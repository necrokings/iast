"""Unit tests for the DynamoDB client wrapper."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.core.config import DynamoDBConfig
from src.db import client as client_module
from src.db.client import DynamoDBClient, get_dynamodb_client


class DynamoDBClientTests(unittest.TestCase):
    """Validate DynamoDB wrapper behavior without touching AWS."""

    def setUp(self) -> None:
        self.config = DynamoDBConfig(
            endpoint="http://localhost:8042",
            region="us-east-1",
            table_name="terminal",
            access_key_id="dummy",
            secret_access_key="dummy",
        )
        resource_patcher = patch("src.db.client.boto3.resource")
        client_patcher = patch("src.db.client.boto3.client")
        self.addCleanup(resource_patcher.stop)
        self.addCleanup(client_patcher.stop)
        self.mock_resource = resource_patcher.start()
        self.mock_client_ctor = client_patcher.start()
        self.mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = self.mock_table
        self.mock_low_level = self.mock_client_ctor.return_value
        self.mock_low_level.describe_table.return_value = {"Table": {}}
        client_module._client = None

    def tearDown(self) -> None:
        client_module._client = None

    def test_constructor_validates_connection(self) -> None:
        DynamoDBClient(self.config)
        self.mock_low_level.describe_table.assert_called_once()
        self.mock_resource.return_value.Table.assert_called_once_with(
            self.config.table_name
        )

    def test_constructor_raises_when_validation_fails(self) -> None:
        self.mock_low_level.describe_table.side_effect = Exception("boom")
        with self.assertRaises(RuntimeError):
            DynamoDBClient(self.config)
        self.mock_low_level.describe_table.side_effect = None

    def test_update_item_builds_expression(self) -> None:
        client = DynamoDBClient(self.config)
        self.mock_table.update_item.return_value = {"Attributes": {"status": "running"}}
        result = client.update_item(
            pk="USER#123",
            sk="SESSION#abc",
            updates={"status": "running", "progress": 50},
        )
        self.assertEqual(result, {"status": "running"})
        kwargs = self.mock_table.update_item.call_args.kwargs
        self.assertEqual(kwargs["Key"], {"PK": "USER#123", "SK": "SESSION#abc"})

    def test_query_helpers_delegate_to_table(self) -> None:
        client = DynamoDBClient(self.config)
        self.mock_table.query.return_value = {"Items": [{"id": 1}]}
        client.query_pk("PK")
        client.query_pk("PK", sk_prefix="SESSION", limit=5)
        client.query_gsi1("email@example.com", sk_prefix="PROFILE")
        client.query_gsi2("GSI2PK", scan_forward=True, limit=2, exclusive_start_key={"PK": "1"})
        self.assertGreaterEqual(self.mock_table.query.call_count, 4)

    def test_domain_specific_helpers(self) -> None:
        client = DynamoDBClient(self.config)
        self.mock_table.query.return_value = {"Items": []}
        client.put_user("u1", "email@example.com", {"extra": "x"})
        client.get_user("u1")
        client.get_user_by_email("email@example.com")
        client.put_session("u1", "sess1", {"status": "active"})
        client.get_user_sessions("u1")
        client.get_session_executions("sess1")
        client.put_execution("sess1", "exec1", {"user_id": "u1"})
        client.update_execution("sess1", "exec1", {"status": "running"})
        client.get_execution_policies("exec1")
        client.put_policy_result("exec1", "policy1", {"status": "pending"})
        client.get_policy_result("exec1", "policy1")
        client.get_user_executions_by_date("u1", "2024-01-01", status="running")
        self.assertTrue(self.mock_table.put_item.called)

    def test_get_execution_by_id_scans_table(self) -> None:
        client = DynamoDBClient(self.config)
        self.mock_table.scan.return_value = {"Items": [{"SK": "EXECUTION#id"}]}
        result = client.get_execution_by_id("id")
        self.assertEqual(result["SK"], "EXECUTION#id")

    def test_singleton_getter(self) -> None:
        with patch.object(client_module, "DynamoDBClient", return_value="instance"):
            first = get_dynamodb_client(self.config)
            second = get_dynamodb_client()
        self.assertEqual(first, "instance")
        self.assertEqual(second, "instance")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

