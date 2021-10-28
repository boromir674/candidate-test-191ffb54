import uuid
from typing import Optional

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.http.request import HttpRequest
from django.test import RequestFactory

from visitors.middleware import VisitorRequestMiddleware, VisitorSessionMiddleware, VisitorCountMiddleware
from visitors.models import Visitor
from visitors.settings import VISITOR_SESSION_KEY


@pytest.fixture
def visitor() -> Visitor:
    return Visitor.objects.create(email="fred@example.com", scope="foo")


@pytest.fixture
def visitor_with_max_usage_reached() -> Visitor:
    """A Visitor who has reached the maximum allowed uses for the link.

    All subsequent requests made by this Visitor should be denied."""
    from django.conf import settings
    return Visitor.objects.create(email="fred@example.com", scope="foo",
        usage_count=settings.DEFAULT_MAX_LINK_USAGES_ALLOWED)


class Session(dict):
    """Fake Session model used to support `session_key` property."""

    @property
    def session_key(self) -> str:
        return "foobar"

    def set_expiry(self, expiry: int) -> None:
        self.expiry = expiry


class TestVisitorMiddlewareBase:
    def request(self, url: str, user: Optional[User] = None) -> HttpRequest:
        factory = RequestFactory()
        request = factory.get(url)
        request.user = user or AnonymousUser()
        request.session = Session()
        return request


@pytest.mark.django_db
class TestVisitorRequestMiddleware(TestVisitorMiddlewareBase):
    def test_no_token(self) -> None:
        request = self.request("/", AnonymousUser())
        middleware = VisitorRequestMiddleware(lambda r: r)
        middleware(request)
        assert not request.user.is_visitor
        assert not request.visitor

    def test_token_does_not_exist(self) -> None:
        request = self.request(f"/?vuid={uuid.uuid4()}")
        middleware = VisitorRequestMiddleware(lambda r: r)
        middleware(request)
        assert not request.user.is_visitor
        assert not request.visitor

    def test_token_is_invalid(self, visitor: Visitor) -> None:
        visitor.deactivate()
        request = self.request(visitor.tokenise("/"))
        middleware = VisitorRequestMiddleware(lambda r: r)
        middleware(request)
        assert not request.user.is_visitor
        assert not request.visitor

    def test_valid_token(self, visitor: Visitor) -> None:
        request = self.request(visitor.tokenise("/"))
        middleware = VisitorRequestMiddleware(lambda r: r)
        middleware(request)
        assert request.user.is_visitor
        assert request.visitor == visitor


@pytest.mark.django_db
class TestVisitorSessionMiddleware(TestVisitorMiddlewareBase):
    def request(
        self,
        url: str,
        user: Optional[User] = None,
        is_visitor: bool = False,
        visitor: Visitor = None,
    ) -> HttpRequest:
        request = super().request(url, user)
        request.user.is_visitor = is_visitor
        request.visitor = visitor
        return request

    def test_visitor(self, visitor: Visitor) -> None:
        """Check that request.visitor is stashed in session."""
        request = self.request("/", is_visitor=True, visitor=visitor)
        assert not request.session.get(VISITOR_SESSION_KEY)
        middleware = VisitorSessionMiddleware(lambda r: r)
        middleware(request)
        assert request.session[VISITOR_SESSION_KEY] == visitor.session_data

    def test_no_visitor_no_session(self) -> None:
        """Check that no visitor on request or session passes."""
        request = self.request("/", is_visitor=False, visitor=None)
        middleware = VisitorSessionMiddleware(lambda r: r)
        middleware(request)
        assert not request.user.is_visitor
        assert not request.visitor

    def test_visitor_in_session(self, visitor: Visitor) -> None:
        """Check no visitor on request, but in session."""
        request = self.request("/", is_visitor=False, visitor=None)
        request.session[VISITOR_SESSION_KEY] = visitor.session_data
        middleware = VisitorSessionMiddleware(lambda r: r)
        middleware(request)
        assert request.user.is_visitor
        assert request.visitor == visitor

    def test_visitor_does_not_exist(self) -> None:
        """Check non-existant visitor in session."""
        request = self.request("/", is_visitor=False, visitor=None)
        request.session[VISITOR_SESSION_KEY] = str(uuid.uuid4())
        middleware = VisitorSessionMiddleware(lambda r: r)
        middleware(request)
        assert not request.user.is_visitor
        assert not request.visitor
        assert not request.session.get(VISITOR_SESSION_KEY)


@pytest.mark.django_db
class TestVisitorCountMiddleware(TestVisitorSessionMiddleware):
    def test_usage_increment(self, visitor: Visitor) -> None:
        """Test that a Visitor Link usage counter increments by 1 when a Visitor makes a request"""
        current_count = visitor.usage_count
        request = self.request("/", is_visitor=True, visitor=visitor)
        middleware = VisitorCountMiddleware(lambda r: r)
        middleware(request)
        visitor.refresh_from_db()
        assert visitor.usage_count == current_count + 1

    def test_non_visitor(self) -> None:
        """Test that the middleware does nothing when it receives a request from a non-visitor."""
        request = self.request("/", is_visitor=False, visitor=None)
        middleware = VisitorCountMiddleware(lambda r: r)
        request_passed_through_middleware = middleware(request)
        assert request_passed_through_middleware == request

    def test_rejection_at_usage_limit(self, visitor_with_max_usage_reached: Visitor) -> None:
        request = self.request("/", is_visitor=True, visitor=visitor_with_max_usage_reached)
        middleware = VisitorCountMiddleware(lambda r: r)
        middleware(request)
        visitor_with_max_usage_reached.refresh_from_db()
        assert visitor_with_max_usage_reached.is_active == False
        assert request.user.is_visitor == False
