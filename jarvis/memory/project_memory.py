"""Project Memory

Tracks project metadata, file structures, and preferences.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import select
from loguru import logger

from jarvis.core.database import get_session
from jarvis.core.models import Project, Preference


class ProjectMemory:
    """Manages project context and metadata."""

    def __init__(self):
        pass

    async def create_project(
        self,
        name: str,
        path: str,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Project:
        """Create a new project entry."""
        async with get_session() as session:
            project = Project(
                name=name,
                path=path,
                description=description,
                task_metadata=metadata or {},
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            logger.info(f"Created project: {name} at {path}")
            return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            return result.scalar_one_or_none()

    async def get_project_by_path(self, path: str) -> Optional[Project]:
        """Get a project by path."""
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.path == path)
            )
            return result.scalar_one_or_none()

    async def list_projects(self) -> list[Project]:
        """List all projects."""
        async with get_session() as session:
            result = await session.execute(select(Project))
            return list(result.scalars().all())

    async def update_project(
        self,
        project_id: str,
        **kwargs,
    ) -> Optional[Project]:
        """Update project metadata."""
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if project:
                for key, value in kwargs.items():
                    if hasattr(project, key):
                        setattr(project, key, value)
                await session.commit()
                await session.refresh(project)
                logger.debug(f"Updated project: {project.name}")

            return project

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        async with get_session() as session:
            result = await session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            if project:
                await session.delete(project)
                await session.commit()
                logger.info(f"Deleted project: {project.name}")
                return True

            return False

    async def set_preference(self, key: str, value: str) -> Preference:
        """Set a user preference."""
        async with get_session() as session:
            result = await session.execute(
                select(Preference).where(Preference.key == key)
            )
            pref = result.scalar_one_or_none()

            if pref:
                pref.value = value
            else:
                pref = Preference(key=key, value=value)
                session.add(pref)

            await session.commit()
            await session.refresh(pref)
            logger.debug(f"Set preference: {key} = {value}")
            return pref

    async def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a user preference."""
        async with get_session() as session:
            result = await session.execute(
                select(Preference).where(Preference.key == key)
            )
            pref = result.scalar_one_or_none()
            return pref.value if pref else default

    async def list_preferences(self) -> dict[str, str]:
        """List all preferences."""
        async with get_session() as session:
            result = await session.execute(select(Preference))
            prefs = result.scalars().all()
            return {p.key: p.value for p in prefs}
