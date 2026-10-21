"""拒否の理由。code はフロントの StorageError の code と同じ名前にする（docs/storage-interface.md）。"""


class ApiError(Exception):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
