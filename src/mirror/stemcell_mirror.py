from abc import ABC, abstractmethod


class StemcellMirror(ABC):
    """Interface for mirroring a stemcell series to an image gallery."""

    @abstractmethod
    def run(self) -> None:
        """Mirror the latest stemcell of this series to the target gallery."""
        raise NotImplementedError
