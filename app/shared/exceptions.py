# -*- coding: utf-8 -*-


class RedirectException(Exception):
    def __init__(self, url: str, status_code: int = 303):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Redirect to {url}")