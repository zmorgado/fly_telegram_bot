from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def search_flights(self, origin, destination, start_date, end_date):
        """Return a list of flight dicts with standardized keys."""
        pass
