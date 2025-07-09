#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simplified Supabase client for reading table content
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

__log__ = logging.getLogger(__name__)


class SupabaseClient:
    """Simplified Supabase client for reading table content"""

    def __init__(self, config=None):
        """
        Initialize Supabase client

        Args:
            config: Configuration object (optional)
        """
        self._engine = None
        self._session_maker = None
        self.db_url = self._get_database_url(config)

        if not self.db_url:
            __log__.warning("No Supabase database connection configured")

    def _get_database_url(self, config=None) -> Optional[str]:
        """Get database URL from config"""
        # Try to get database URL from config
        if config and config.get("supabase", {}).get("database_url"):
            return config["supabase"]["database_url"]

        __log__.warning("No Supabase database URL found in configuration")
        return None

    @property
    def engine(self):
        """Get SQLAlchemy engine"""
        if self._engine is None:
            if not self.db_url:
                raise ValueError("No database URL configured")

            __log__.info("Creating database engine")
            self._engine = create_engine(
                self.db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={"sslmode": "require", "connect_timeout": 30, "options": "-c timezone=utc"},
            )
        return self._engine

    def get_session(self):
        """Get a new database session"""
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.engine)
        return self._session_maker()

    def read_table(
        self,
        table_name: str,
        limit: int = 100,
        offset: int = 0,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read data from a table

        Args:
            table_name: Name of the table to read
            limit: Maximum number of rows to return
            offset: Number of rows to skip
            columns: Specific columns to select (if None, selects all)
            filters: Dictionary of column: value filters

        Returns:
            List of dictionaries representing rows
        """
        try:
            # Build query
            column_str = "*" if not columns else ", ".join(columns)
            query = f"SELECT {column_str} FROM {table_name}"

            # Add WHERE clause if filters provided
            if filters:
                where_conditions = []
                for column, value in filters.items():
                    if isinstance(value, str):
                        where_conditions.append(f"{column} = '{value}'")
                    else:
                        where_conditions.append(f"{column} = {value}")

                if where_conditions:
                    query += " WHERE " + " AND ".join(where_conditions)

            # Add LIMIT and OFFSET
            query += f" LIMIT {limit} OFFSET {offset}"

            return self.execute_query(query)

        except Exception as e:
            __log__.error(f"Error reading table {table_name}: {e}")
            raise

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results

        Args:
            query: SQL query string

        Returns:
            List of dictionaries representing rows
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query))
                rows = []
                for row in result:
                    # Convert row to dictionary
                    row_dict = dict(row._mapping)
                    rows.append(row_dict)
                return rows

        except SQLAlchemyError as e:
            __log__.error(f"Database error executing query: {e}")
            raise
        except Exception as e:
            __log__.error(f"Error executing query: {e}")
            raise

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            __log__.info("Database connection successful")
            return True
        except Exception as e:
            __log__.error(f"Database connection failed: {e}")
            return False

    def close(self):
        """Close database connections"""
        if self._engine:
            self._engine.dispose()
            __log__.info("Database connections closed")
