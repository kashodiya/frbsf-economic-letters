"""
Database models and operations for FRBSF Economic Letters application
"""
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import json
import aiosqlite
import asyncio

# Database configuration
DATABASE_URL = "sqlite:///./economic_letters.db"
CACHE_EXPIRY_HOURS = 24  # Cache expires after 24 hours

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EconomicLetter(Base):
    """Model for storing economic letters"""
    __tablename__ = "economic_letters"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    date = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Add index for faster queries
    __table_args__ = (
        Index('idx_url_scraped', 'url', 'scraped_at'),
        Index('idx_date_scraped', 'date', 'scraped_at'),
    )


class Insight(Base):
    """Model for storing AI-generated insights"""
    __tablename__ = "insights"
    
    id = Column(Integer, primary_key=True, index=True)
    letter_url = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    question_hash = Column(String, nullable=False, index=True)  # Hash of question for quick lookup
    insight = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Add composite index for faster lookups
    __table_args__ = (
        Index('idx_letter_question', 'letter_url', 'question_hash'),
    )


class CacheMetadata(Base):
    """Model for tracking cache status and metadata"""
    __tablename__ = "cache_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True, nullable=False)
    cache_type = Column(String, nullable=False)  # 'letters_list', 'letter_content', etc.
    last_updated = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_valid = Column(Boolean, default=True)
    extra_data = Column(Text)  # JSON string for additional metadata


class DatabaseManager:
    """Database operations manager"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def get_db(self) -> Session:
        """Get database session"""
        db = self.SessionLocal()
        try:
            return db
        except Exception:
            db.close()
            raise
    
    def close_db(self, db: Session):
        """Close database session"""
        db.close()
    
    # Economic Letters operations
    def get_letters_from_cache(self, limit: int = 10, offset: int = 0) -> tuple[List[Dict[str, Any]], bool]:
        """Get cached economic letters with pagination"""
        db = self.get_db()
        try:
            # Check if cache is still valid
            cache_key = "letters_list"
            cache_entry = db.query(CacheMetadata).filter(
                CacheMetadata.cache_key == cache_key,
                CacheMetadata.expires_at > datetime.utcnow(),
                CacheMetadata.is_valid == True
            ).first()
            
            if not cache_entry:
                return [], False
            
            # Get letters from database with pagination
            letters_query = db.query(EconomicLetter).order_by(
                EconomicLetter.scraped_at.desc()
            )
            
            # Get total count for has_more calculation
            total_count = letters_query.count()
            
            # Apply pagination
            letters = letters_query.offset(offset).limit(limit).all()
            
            # Check if there are more letters
            has_more = (offset + limit) < total_count
            
            letters_data = [
                {
                    "title": letter.title,
                    "url": letter.url,
                    "date": letter.date,
                    "summary": letter.summary,
                    "content": letter.content
                }
                for letter in letters
            ]
            
            return letters_data, has_more
        finally:
            self.close_db(db)
    
    def store_letters(self, letters_data: List[Dict[str, Any]]) -> bool:
        """Store economic letters in database"""
        db = self.get_db()
        try:
            # Store or update letters
            for letter_data in letters_data:
                existing_letter = db.query(EconomicLetter).filter(
                    EconomicLetter.url == letter_data["url"]
                ).first()
                
                if existing_letter:
                    # Update existing letter
                    existing_letter.title = letter_data["title"]
                    existing_letter.date = letter_data["date"]
                    existing_letter.content = letter_data["content"]
                    existing_letter.summary = letter_data["summary"]
                    existing_letter.updated_at = datetime.utcnow()
                else:
                    # Create new letter
                    new_letter = EconomicLetter(
                        url=letter_data["url"],
                        title=letter_data["title"],
                        date=letter_data["date"],
                        content=letter_data["content"],
                        summary=letter_data["summary"]
                    )
                    db.add(new_letter)
            
            # Update cache metadata
            cache_key = "letters_list"
            cache_entry = db.query(CacheMetadata).filter(
                CacheMetadata.cache_key == cache_key
            ).first()
            
            expires_at = datetime.utcnow() + timedelta(hours=CACHE_EXPIRY_HOURS)
            
            if cache_entry:
                cache_entry.last_updated = datetime.utcnow()
                cache_entry.expires_at = expires_at
                cache_entry.is_valid = True
            else:
                new_cache = CacheMetadata(
                    cache_key=cache_key,
                    cache_type="letters_list",
                    expires_at=expires_at,
                    extra_data=json.dumps({"count": len(letters_data)})
                )
                db.add(new_cache)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"Error storing letters: {e}")
            return False
        finally:
            self.close_db(db)
    
    def is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        db = self.get_db()
        try:
            cache_entry = db.query(CacheMetadata).filter(
                CacheMetadata.cache_key == cache_key,
                CacheMetadata.expires_at > datetime.utcnow(),
                CacheMetadata.is_valid == True
            ).first()
            return cache_entry is not None
        finally:
            self.close_db(db)
    
    # Insights operations
    def get_cached_insight(self, letter_url: str, question: str) -> Optional[str]:
        """Get cached insight for a specific question about a letter"""
        db = self.get_db()
        try:
            question_hash = self._hash_question(question)
            insight = db.query(Insight).filter(
                Insight.letter_url == letter_url,
                Insight.question_hash == question_hash
            ).first()
            
            return insight.insight if insight else None
        finally:
            self.close_db(db)
    
    def store_insight(self, letter_url: str, question: str, insight_text: str) -> bool:
        """Store an AI-generated insight"""
        db = self.get_db()
        try:
            question_hash = self._hash_question(question)
            
            # Check if insight already exists
            existing_insight = db.query(Insight).filter(
                Insight.letter_url == letter_url,
                Insight.question_hash == question_hash
            ).first()
            
            if existing_insight:
                # Update existing insight
                existing_insight.insight = insight_text
                existing_insight.created_at = datetime.utcnow()
            else:
                # Create new insight
                new_insight = Insight(
                    letter_url=letter_url,
                    question=question,
                    question_hash=question_hash,
                    insight=insight_text
                )
                db.add(new_insight)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            print(f"Error storing insight: {e}")
            return False
        finally:
            self.close_db(db)
    
    def _hash_question(self, question: str) -> str:
        """Create a hash of the question for efficient lookups"""
        return hashlib.md5(question.lower().strip().encode()).hexdigest()
    
    # Question history operations
    def get_question_history(self, letter_url: str) -> List[Dict[str, Any]]:
        """Get question history for a specific letter"""
        db = self.get_db()
        try:
            insights = db.query(Insight).filter(
                Insight.letter_url == letter_url
            ).order_by(Insight.created_at.desc()).all()
            
            return [
                {
                    "id": insight.id,
                    "question": insight.question,
                    "insight": insight.insight,
                    "created_at": insight.created_at.isoformat()
                }
                for insight in insights
            ]
        finally:
            self.close_db(db)
    
    def delete_question(self, question_id: int) -> bool:
        """Delete a specific question and its insight"""
        db = self.get_db()
        try:
            insight = db.query(Insight).filter(Insight.id == question_id).first()
            if insight:
                db.delete(insight)
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            print(f"Error deleting question: {e}")
            return False
        finally:
            self.close_db(db)
    
    # Cache management
    def clear_cache(self, cache_type: Optional[str] = None):
        """Clear cache entries"""
        db = self.get_db()
        try:
            query = db.query(CacheMetadata)
            if cache_type:
                query = query.filter(CacheMetadata.cache_type == cache_type)
            
            query.update({"is_valid": False})
            db.commit()
        finally:
            self.close_db(db)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        db = self.get_db()
        try:
            total_letters = db.query(EconomicLetter).count()
            total_insights = db.query(Insight).count()
            valid_caches = db.query(CacheMetadata).filter(
                CacheMetadata.is_valid == True,
                CacheMetadata.expires_at > datetime.utcnow()
            ).count()
            
            return {
                "total_letters": total_letters,
                "total_insights": total_insights,
                "valid_caches": valid_caches,
                "database_size": "N/A"  # Could implement file size check
            }
        finally:
            self.close_db(db)


# Global database manager instance
db_manager = DatabaseManager()


def init_database():
    """Initialize database and create tables"""
    print("🗄️  Initializing SQLite database...")
    db_manager.create_tables()
    print("✅ Database initialized successfully")


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    return db_manager