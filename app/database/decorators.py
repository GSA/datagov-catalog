from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def paginate(fn: F) -> F:
    @wraps(fn)
    def _impl(self, *args, **kwargs):
        query = fn(self, *args, **kwargs)

        if isinstance(query, list):
            return query

        if kwargs.get("count") is True:
            return query

        if kwargs.get("paginate") is False:
            return query.all()

        config = self.pagination

        requested_per_page = kwargs.get("per_page")
        per_page = (
            config.entries_per_page
            if requested_per_page is None
            else requested_per_page
        )

        requested_page = kwargs.get("page")
        page = config.start_page if requested_page is None else requested_page

        per_page = max(
            min(per_page, config.max_entries_per_page),
            1,
        )
        page = max(page, config.start_page)

        offset = (page - config.start_page) * per_page

        return query.limit(per_page).offset(offset).all()

    return _impl
