"""Unit tests for the DynamoDB client wrapper."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.core.config import DynamoDBConfig
from src.db import client as client_module
from src.db.client import DynamoDBClient, get_dynamodb_client


class DynamoDBClientTests(unittest.TestCase):
    """Validate how we talk to DynamoDB."""

    def setUp(self) -> None:
        self.config = DynamoDBConfig(
            endpoint="http://localhost:8042",
            region="us-east-1",
            table_name="terminal",
            access_key_id="dummy",
            secret_access_key="dummy",
        )
        self.resource_patcher = patch("src.db.client.boto3.resource")
        self.client_patcher = patch("src.db.client.boto3.client")
        self.mock_resource = self.resource_patcher.start()
        self.mock_client_ctor = self.client_patcher.start()
        self.addCleanup(self.resource_patcher.stop)
        self.addCleanup(self.client_patcher.stop)

        self.mock_table = MagicMock()
        self.mock_resource.return_value.Table.return_value = self.mock_table
        self.mock_low_level = self.mock_client_ctor.return_value
        self.mock_low_level.describe_table.return_value = {"Table": {}}

        client_module._client = None

    def tearDown(self) -> None:
        client_module._client = None

    def test_constructor_validates_connection(self) -> None:
        DynamoDBClient(self.config)

        self.mock_low_level.describe_table.assert_called_once_with(
            TableName=self.config.table_name
        )
        self.mock_resource.return_value.Table.assert_called_once_with(
            self.config.table_name
        )

    def test_constructor_raises_when_validation_fails(self) -> None:
        self.mock_low_level.describe_table.side_effect = Exception("boom")

        with self.assertRaises(RuntimeError) as ctx:
            DynamoDBClient(self.config)

        self.assertIn("Cannot connect to DynamoDB", str(ctx.exception))

        # Reset side effect for other tests
        self.mock_low_level.describe_table.side_effect = None

    def test_update_item_builds_update_expression(self) -> None:
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
        self.assertEqual(
            kwargs["UpdateExpression"], "SET #attr0 = :val0, #attr1 = :val1"
        )
        self.assertEqual(
            kwargs["ExpressionAttributeNames"],
            {"#attr0": "status", "#attr1": "progress"},
        )
        self.assertEqual(
            kwargs["ExpressionAttributeValues"],
            {":val0": "running", ":val1": 50},
        )

    def test_get_dynamodb_client_returns_singleton(self) -> None:
        first = get_dynamodb_client(self.config)
        second = get_dynamodb_client()

        self.assertIs(first, second)

