# ============================================================================
# DynamoDB Client - Single Table Design
# ============================================================================
"""
DynamoDB client wrapper for single table design.

Table: terminal
===============
PK                    SK                        Entity
──────────────────────────────────────────────────────────
USER#<userId>         PROFILE                   User profile
USER#<userId>         SESSION#<sessionId>       User's session
SESSION#<sessionId>   EXECUTION#<execId>        Session's AST execution
EXECUTION#<execId>    POLICY#<policyNum>        Execution's policy result

GSI1: GSI1PK (email) for user lookup by email
GSI2: GSI2PK (USER#<userId>#DATE#<date>), GSI2SK (started_at) for user's executions by date
"""

from datetime import datetime
from typing import Any

import boto3
import structlog
from boto3.dynamodb.conditions import Key

from ..core.config import DynamoDBConfig

log = structlog.get_logger()


# Key prefixes for single table design
class KeyPrefix:
    USER = "USER#"
    SESSION = "SESSION#"
    EXECUTION = "EXECUTION#"
    POLICY = "POLICY#"
    PROFILE = "PROFILE"


class DynamoDBClient:
    """
    DynamoDB client wrapper for single table design.
    """

    def __init__(self, config: DynamoDBConfig) -> None:
        self._table_name = config.table_name
        self._resource = boto3.resource(
            "dynamodb",
            endpoint_url=config.endpoint,
            region_name=config.region,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )
        self._client = boto3.client(
            "dynamodb",
            endpoint_url=config.endpoint,
            region_name=config.region,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )
        self._table = self._resource.Table(config.table_name)  # type: ignore[attr-defined]

        # Validate connection by describing the table
        try:
            self._client.describe_table(TableName=config.table_name)
            log.info("DynamoDB connection validated")
        except Exception as e:
            log.error("DynamoDB connection failed", error=str(e))
            raise RuntimeError(f"Cannot connect to DynamoDB: {e}")

        log.info("DynamoDB client initialized", endpoint=config.endpoint, table=config.table_name)

    @property
    def table(self) -> Any:
        """Get the table resource."""
        return self._table

    # -------------------------------------------------------------------------
    # Generic Operations
    # -------------------------------------------------------------------------

    def put_item(self, item: dict[str, Any]) -> None:
        """Put an item into the table."""
        self._table.put_item(Item=item)

    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        """Get an item by primary key (PK + SK)."""
        response = self._table.get_item(Key={"PK": pk, "SK": sk})
        return response.get("Item")

    def update_item(
        self,
        pk: str,
        sk: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an item with given attributes."""
        # Build update expression
        update_parts = []
        expression_values = {}
        expression_names = {}

        for i, (attr, value) in enumerate(updates.items()):
            placeholder = f":val{i}"
            name_placeholder = f"#attr{i}"
            update_parts.append(f"{name_placeholder} = {placeholder}")
            expression_values[placeholder] = value
            expression_names[name_placeholder] = attr

        update_expression = "SET " + ", ".join(update_parts)

        response = self._table.update_item(
            Key={"PK": pk, "SK": sk},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    def delete_item(self, pk: str, sk: str) -> None:
        """Delete an item by primary key."""
        self._table.delete_item(Key={"PK": pk, "SK": sk})

    def query_pk(
        self,
        pk: str,
        sk_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query items by PK, optionally filtering by SK prefix."""
        if sk_prefix:
            key_condition = Key("PK").eq(pk) & Key("SK").begins_with(sk_prefix)
        else:
            key_condition = Key("PK").eq(pk)

        kwargs: dict[str, Any] = {"KeyConditionExpression": key_condition}
        if limit:
            kwargs["Limit"] = limit

        response = self._table.query(**kwargs)
        return response.get("Items", [])

    def query_gsi1(
        self,
        gsi1pk: str,
        sk_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query GSI1 by GSI1PK (e.g., email lookup)."""
        if sk_prefix:
            key_condition = Key("GSI1PK").eq(gsi1pk) & Key("SK").begins_with(sk_prefix)
        else:
            key_condition = Key("GSI1PK").eq(gsi1pk)

        kwargs: dict[str, Any] = {
            "IndexName": "GSI1",
            "KeyConditionExpression": key_condition,
        }
        if limit:
            kwargs["Limit"] = limit

        response = self._table.query(**kwargs)
        return response.get("Items", [])

    def query_gsi2(
        self,
        gsi2pk: str,
        scan_forward: bool = False,
        limit: int | None = None,
        exclusive_start_key: dict[str, Any] | None = None,
        filter_expression: Any | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """
        Query GSI2 by GSI2PK (e.g., user's executions by date).

        Returns a tuple of (items, last_evaluated_key for pagination).
        """
        key_condition = Key("GSI2PK").eq(gsi2pk)

        kwargs: dict[str, Any] = {
            "IndexName": "GSI2",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward,  # False = newest first
        }
        if limit:
            kwargs["Limit"] = limit
        if exclusive_start_key:
            kwargs["ExclusiveStartKey"] = exclusive_start_key
        if filter_expression:
            kwargs["FilterExpression"] = filter_expression

        response = self._table.query(**kwargs)
        return response.get("Items", []), response.get("LastEvaluatedKey")

    # -------------------------------------------------------------------------
    # User Operations
    # -------------------------------------------------------------------------

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user profile by ID."""
        return self.get_item(f"{KeyPrefix.USER}{user_id}", KeyPrefix.PROFILE)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user profile by email (via GSI1)."""
        items = self.query_gsi1(email, sk_prefix=KeyPrefix.PROFILE, limit=1)
        return items[0] if items else None

    def put_user(self, user_id: str, email: str, data: dict[str, Any]) -> None:
        """Create or update a user."""
        item = {
            "PK": f"{KeyPrefix.USER}{user_id}",
            "SK": KeyPrefix.PROFILE,
            "GSI1PK": email,
            "user_id": user_id,
            "email": email,
            **data,
        }
        self.put_item(item)

    def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all sessions for a user."""
        return self.query_pk(f"{KeyPrefix.USER}{user_id}", sk_prefix=KeyPrefix.SESSION)

    # -------------------------------------------------------------------------
    # Session Operations
    # -------------------------------------------------------------------------

    def put_session(self, user_id: str, session_id: str, data: dict[str, Any]) -> None:
        """Create a session for a user."""
        item = {
            "PK": f"{KeyPrefix.USER}{user_id}",
            "SK": f"{KeyPrefix.SESSION}{session_id}",
            "user_id": user_id,
            "session_id": session_id,
            **data,
        }
        self.put_item(item)

    def get_session_executions(self, session_id: str) -> list[dict[str, Any]]:
        """Get all AST executions for a session."""
        return self.query_pk(f"{KeyPrefix.SESSION}{session_id}", sk_prefix=KeyPrefix.EXECUTION)

    # -------------------------------------------------------------------------
    # AST Execution Operations
    # -------------------------------------------------------------------------

    def put_execution(self, session_id: str, execution_id: str, data: dict[str, Any]) -> None:
        """Create an AST execution record."""
        # Extract user_id and started_at for GSI2
        user_id = data.get("user_id", "anonymous")
        started_at = data.get("started_at", datetime.now().isoformat())

        # Parse date from started_at for GSI2PK
        if isinstance(started_at, str):
            date_str = started_at[:10]  # YYYY-MM-DD
        else:
            date_str = started_at.strftime("%Y-%m-%d")

        item = {
            "PK": f"{KeyPrefix.SESSION}{session_id}",
            "SK": f"{KeyPrefix.EXECUTION}{execution_id}",
            "GSI2PK": f"{KeyPrefix.USER}{user_id}#DATE#{date_str}",
            "GSI2SK": started_at,
            "session_id": session_id,
            "execution_id": execution_id,
            **data,
        }
        self.put_item(item)

    def update_execution(
        self, session_id: str, execution_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an AST execution record."""
        return self.update_item(
            f"{KeyPrefix.SESSION}{session_id}",
            f"{KeyPrefix.EXECUTION}{execution_id}",
            updates,
        )

    def get_execution_policies(self, execution_id: str) -> list[dict[str, Any]]:
        """Get all policy results for an execution."""
        return self.query_pk(f"{KeyPrefix.EXECUTION}{execution_id}", sk_prefix=KeyPrefix.POLICY)

    def get_user_executions_by_date(
        self,
        user_id: str,
        date: str,
        status: str | None = None,
        limit: int = 20,
        cursor: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """
        Get user's executions for a specific date.

        Args:
            user_id: User ID
            date: Date in YYYY-MM-DD format
            status: Optional status filter (running, success, failed, paused, cancelled)
            limit: Maximum number of items to return
            cursor: Pagination cursor (LastEvaluatedKey from previous query)

        Returns:
            Tuple of (executions, next_cursor)
        """
        from boto3.dynamodb.conditions import Attr

        gsi2pk = f"{KeyPrefix.USER}{user_id}#DATE#{date}"

        filter_expr = None
        if status:
            filter_expr = Attr("status").eq(status)

        return self.query_gsi2(
            gsi2pk=gsi2pk,
            scan_forward=False,  # Newest first
            limit=limit,
            exclusive_start_key=cursor,
            filter_expression=filter_expr,
        )

    def get_execution_by_id(self, execution_id: str) -> dict[str, Any] | None:
        """
        Get an execution by its ID.

        Since we don't know the session_id, we need to do a GSI lookup or scan.
        For now, we'll query by execution_id prefix in PK.
        """
        # Query using execution_id as PK prefix (for policy lookups)
        # We need to find the execution record which has PK=SESSION#... and SK=EXECUTION#<id>
        # This requires a scan with filter, which is not ideal but works for now
        response = self._table.scan(
            FilterExpression=Key("SK").eq(f"{KeyPrefix.EXECUTION}{execution_id}"),
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None

    # -------------------------------------------------------------------------
    # Policy Result Operations
    # -------------------------------------------------------------------------

    def put_policy_result(
        self, execution_id: str, policy_number: str, data: dict[str, Any]
    ) -> None:
        """Create a policy result record."""
        item = {
            "PK": f"{KeyPrefix.EXECUTION}{execution_id}",
            "SK": f"{KeyPrefix.POLICY}{policy_number}",
            "execution_id": execution_id,
            "policy_number": policy_number,
            **data,
        }
        self.put_item(item)

    def get_policy_result(self, execution_id: str, policy_number: str) -> dict[str, Any] | None:
        """Get a specific policy result."""
        return self.get_item(
            f"{KeyPrefix.EXECUTION}{execution_id}",
            f"{KeyPrefix.POLICY}{policy_number}",
        )


# Singleton instance
_client: DynamoDBClient | None = None


def get_dynamodb_client(config: DynamoDBConfig | None = None) -> DynamoDBClient:
    """Get the singleton DynamoDB client instance."""
    global _client
    if _client is None:
        if config is None:
            from ..core.config import get_config

            config = get_config().dynamodb
        _client = DynamoDBClient(config)
    return _client
