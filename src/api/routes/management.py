from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Query, Response
from src.api.dependencies import Token
from src.api.schemas.common import ERROR_RESPONSES
from src.api.schemas.management import (CreateDepartment, CreatePosting, CreateUser, DepartmentPage,
    DepartmentView, PageFilters, PostingFilters, PostingPage, PostingView, UserActive, UserFilters, UserPage, UserView)
from src.api.execution import execute
from src.management import service

router = APIRouter(prefix="/api/admin", tags=["administration"], responses=ERROR_RESPONSES)


@router.get("/departments", response_model=DepartmentPage)
def departments(token: Token, response: Response, filters: Annotated[PageFilters, Query()]):
    return execute(token, response, service.departments, **filters.model_dump())


@router.post("/departments", response_model=DepartmentView, status_code=201)
def create_department(body: CreateDepartment, token: Token, response: Response):
    return execute(token, response, service.create_department, **body.model_dump())


@router.get("/postings", response_model=PostingPage)
def postings(token: Token, response: Response, filters: Annotated[PostingFilters, Query()]):
    return execute(token, response, service.postings, **filters.model_dump())


@router.post("/postings", response_model=PostingView, status_code=201)
def create_posting(body: CreatePosting, token: Token, response: Response):
    return execute(token, response, service.create_posting, **body.model_dump())


@router.get("/users", response_model=UserPage)
def users(token: Token, response: Response, filters: Annotated[UserFilters, Query()]):
    return execute(token, response, service.users, **filters.model_dump())


@router.post("/users", response_model=UserView, status_code=201)
def create_user(body: CreateUser, token: Token, response: Response):
    return execute(token, response, service.create_user, **body.model_dump())


@router.post("/users/{user_id}/active")
def active(user_id: UUID, body: UserActive, token: Token, response: Response):
    return execute(token, response, service.set_active, str(user_id), body.active)
