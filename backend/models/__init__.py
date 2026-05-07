"""Database models for the application."""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    """User model for authentication and document ownership."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    document_versions = relationship("DocumentVersion", back_populates="creator", cascade="all")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Document(Base):
    """Document model representing a collaborative note."""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, default="Untitled Document")
    content = Column(Text, default="")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1, nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="documents")
    versions = relationship(
        "DocumentVersion", 
        back_populates="document", 
        cascade="all, delete-orphan",
        order_by="DocumentVersion.created_at.desc()"
    )
    collaborators = relationship(
        "DocumentCollaborator", 
        back_populates="document", 
        cascade="all, delete-orphan"
    )
    
    # Indexes for performance
    __table_args__ = (
        Index("ix_documents_owner_id", "owner_id"),
        Index("ix_documents_updated_at", "updated_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}')>"


class DocumentVersion(Base):
    """Immutable snapshot of document content for version history."""
    
    __tablename__ = "document_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    version_number = Column(Integer, nullable=False)
    change_summary = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="versions")
    creator = relationship("User", back_populates="document_versions")
    
    # Indexes
    __table_args__ = (
        Index("ix_versions_document_id", "document_id"),
        Index("ix_versions_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentVersion(id={self.id}, doc_id={self.document_id}, v={self.version_number})>"


class DocumentCollaborator(Base):
    """Many-to-many relationship for document collaborators."""
    
    __tablename__ = "document_collaborators"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String(20), default="edit")  # 'view', 'edit', 'admin'
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="collaborators")
    
    __table_args__ = (
        Index("ix_collab_doc_user", "document_id", "user_id", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<DocumentCollaborator(doc={self.document_id}, user={self.user_id})>"


class OperationLog(Base):
    """Log of operations for conflict resolution and audit trail."""
    
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    operation_type = Column(String(50), nullable=False)  # 'insert', 'delete', 'update'
    operation_data = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    vector_clock = Column(JSON)  # For conflict resolution
    
    __table_args__ = (
        Index("ix_ops_document_id", "document_id"),
        Index("ix_ops_timestamp", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<OperationLog(id={self.id}, type={self.operation_type})>"
