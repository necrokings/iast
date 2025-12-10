# ============================================================================
# AST - Automated Streamlined Transactions
# ============================================================================
"""
AST (Automated Streamlined Transaction) scripts for TN3270 terminal automation.

Each AST is a self-contained automation script that performs a specific
transaction or workflow on the mainframe.

The base infrastructure (AST class, result types, helpers) is in src/core/ast/.
This folder contains the actual AST implementations.
"""

from ..core.ast import (
    AST,
    ASTResult,
    ASTStatus,
    ItemResult,
    ProgressCallback,
    ItemResultCallback,
)
from .login import LoginAST

__all__ = [
    "AST",
    "ASTResult",
    "ASTStatus",
    "ItemResult",
    "ProgressCallback",
    "ItemResultCallback",
    "LoginAST",
]
