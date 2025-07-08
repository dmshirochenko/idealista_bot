#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple Supabase client using SQLAlchemy ORM for reading existing tables
"""

import os
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, MetaData, Table, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

__log__ = logging.getLogger(__name__)

class SupabaseClient:
    """Simple Supabase client using SQLAlchemy for reading existing tables"""
    
    def __init__(self, config=None):
        """
        Initialize Supabase client
        
        Args:
            config: Configuration object (optional)
        """
        self.config = config
        self._engine = None
        self._session_maker = None
        self._base = None
        self._metadata = None
        
        # Get connection details
        self._setup_connection()
    
    def _setup_connection(self):
        """Setup database connection from config or environment variables"""
        # Try to get from config first
        if self.config:
            supabase_config = self.config.get('supabase', {})
            self.db_url = supabase_config.get('database_url')
            self.host = supabase_config.get('host')
            self.database = supabase_config.get('database', 'postgres')
            self.username = supabase_config.get('username', 'postgres')
            self.password = supabase_config.get('password')
            self.port = supabase_config.get('port', 5432)
        else:
            # Fallback to environment variables
            self.db_url = None
            self.host = None
            self.database = 'postgres'
            self.username = 'postgres'
            self.password = None
            self.port = 5432
        
        # Try environment variables
        if not self.db_url:
            self.db_url = os.getenv('SUPABASE_DATABASE_URL')
        
        if not self.host:
            self.host = os.getenv('SUPABASE_HOST')
        
        if not self.password:
            self.password = os.getenv('SUPABASE_PASSWORD')
        
        # Build connection string if not provided directly
        if not self.db_url and self.host and self.password:
            # Default to transaction pooler (port 6543) for better performance
            if self.port == 5432:
                __log__.info("Using Session pooler (port 5432)")
                self.db_url = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
            else:
                __log__.info("Using Transaction pooler (port 6543)")  
                self.db_url = f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?pgbouncer=true"
        
        if not self.db_url:
            __log__.warning("No Supabase database connection configured")
    
    @property
    def engine(self):
        """Get SQLAlchemy engine"""
        if self._engine is None:
            if not self.db_url:
                raise ValueError("No database URL configured")
            
            __log__.info("Creating database engine")
            self._engine = create_engine(
                self.db_url,
                echo=False,  # Set to True for SQL query logging
                pool_pre_ping=True,
                # Connection args optimized for Supabase
                connect_args={
                    "sslmode": "require",
                    "gssencmode": "disable",  # Disable GSSAPI to avoid negotiation issues
                    "connect_timeout": 30,
                    "options": "-c timezone=utc"
                }
            )
        return self._engine
    
    @property
    def session_maker(self):
        """Get SQLAlchemy session maker"""
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.engine)
        return self._session_maker
    
    def get_session(self):
        """Get a new database session"""
        return self.session_maker()
    
    def reflect_tables(self):
        """Reflect existing database tables"""
        if self._metadata is None:
            __log__.info("Reflecting database tables")
            self._metadata = MetaData()
            self._metadata.reflect(bind=self.engine)
            
            # Create automap base for ORM access
            self._base = automap_base(metadata=self._metadata)
            self._base.prepare()
        
        return self._metadata
    
    def get_table_names(self, schema: str = None) -> List[str]:
        """Get list of all table names"""
        metadata = self.reflect_tables()
        table_names = list(metadata.tables.keys())
        
        # Filter out system tables if no specific schema requested
        if schema is None:
            # Filter out common system/internal tables
            filtered_names = [
                name for name in table_names 
                if not name.startswith(('pg_', 'information_schema', 'auth.', 'storage.', 'realtime.'))
            ]
            return filtered_names
        
        return table_names
    
    def get_table(self, table_name: str):
        """Get SQLAlchemy Table object"""
        metadata = self.reflect_tables()
        if table_name not in metadata.tables:
            raise ValueError(f"Table '{table_name}' not found")
        return metadata.tables[table_name]
    
    def get_table_class(self, table_name: str):
        """Get ORM class for table"""
        self.reflect_tables()
        if not hasattr(self._base.classes, table_name):
            raise ValueError(f"Table class '{table_name}' not found")
        return getattr(self._base.classes, table_name)
    
    def read_table(self, table_name: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Read data from a table
        
        Args:
            table_name: Name of the table to read
            limit: Maximum number of rows to return
            offset: Number of rows to skip
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            table_class = self.get_table_class(table_name)
            
            with self.get_session() as session:
                query = session.query(table_class).offset(offset).limit(limit)
                results = query.all()
                
                # Convert to dictionaries
                rows = []
                for row in results:
                    row_dict = {}
                    for column in row.__table__.columns:
                        value = getattr(row, column.name)
                        # Handle datetime serialization
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        row_dict[column.name] = value
                    rows.append(row_dict)
                
                return rows
        
        except SQLAlchemyError as e:
            __log__.error(f"Database error reading table {table_name}: {e}")
            raise
        except Exception as e:
            __log__.error(f"Error reading table {table_name}: {e}")
            raise
    
    def query_table(self, table_name: str, filters: Dict[str, Any] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query a table with filters
        
        Args:
            table_name: Name of the table to query
            filters: Dictionary of column: value filters
            limit: Maximum number of rows to return
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            table_class = self.get_table_class(table_name)
            
            with self.get_session() as session:
                query = session.query(table_class)
                
                # Apply filters
                if filters:
                    for column, value in filters.items():
                        if hasattr(table_class, column):
                            query = query.filter(getattr(table_class, column) == value)
                
                query = query.limit(limit)
                results = query.all()
                
                # Convert to dictionaries
                rows = []
                for row in results:
                    row_dict = {}
                    for column in row.__table__.columns:
                        value = getattr(row, column.name)
                        # Handle datetime serialization
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        row_dict[column.name] = value
                    rows.append(row_dict)
                
                return rows
        
        except Exception as e:
            __log__.error(f"Error querying table {table_name}: {e}")
            raise
    
    def get_table_count(self, table_name: str, filters: Dict[str, Any] = None) -> int:
        """
        Get row count for a table
        
        Args:
            table_name: Name of the table
            filters: Optional filters to apply
            
        Returns:
            Number of rows in the table
        """
        try:
            table_class = self.get_table_class(table_name)
            
            with self.get_session() as session:
                query = session.query(table_class)
                
                # Apply filters if provided
                if filters:
                    for column, value in filters.items():
                        if hasattr(table_class, column):
                            query = query.filter(getattr(table_class, column) == value)
                
                return query.count()
        
        except Exception as e:
            __log__.error(f"Error counting rows in table {table_name}: {e}")
            raise
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get schema information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with column information
        """
        table = self.get_table(table_name)
        
        schema = {
            'table_name': table_name,
            'columns': []
        }
        
        for column in table.columns:
            column_info = {
                'name': column.name,
                'type': str(column.type),
                'nullable': column.nullable,
                'primary_key': column.primary_key,
                'foreign_keys': [str(fk) for fk in column.foreign_keys]
            }
            schema['columns'].append(column_info)
        
        return schema
    
    def execute_raw_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query
        
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
