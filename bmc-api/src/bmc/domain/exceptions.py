class ExpertNameNotFound(Exception):
    """Exception raised when a philosopher's name is not found."""

    def __init__(self, philosopher_id: str):
        self.message = f"Philosopher name for {philosopher_id} not found."
        super().__init__(self.message)


class ExpertPerspectiveNotFound(Exception):
    """Exception raised when a philosopher's perspective is not found."""

    def __init__(self, philosopher_id: str):
        self.message = f"Philosopher perspective for {philosopher_id} not found."
        super().__init__(self.message)


class ExpertStyleNotFound(Exception):
    """Exception raised when a philosopher's style is not found."""

    def __init__(self, philosopher_id: str):
        self.message = f"Philosopher style for {philosopher_id} not found."
        super().__init__(self.message)


class ExpertContextNotFound(Exception):
    """Exception raised when a philosopher's context is not found."""

    def __init__(self, philosopher_id: str):
        self.message = f"Philosopher context for {philosopher_id} not found."
        super().__init__(self.message)
