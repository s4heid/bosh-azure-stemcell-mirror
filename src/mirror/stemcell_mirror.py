from abc import ABC, abstractmethod


class StemcellMirror(ABC):
    """Interface for mirroring a stemcell series to an image gallery."""

    #: Stable identifier used to select this mirror via configuration
    #: (e.g. ``boshio/ubuntu-jammy``). Concrete subclasses must set it.
    name: str = ""

    @abstractmethod
    def run(self) -> None:
        """Mirror the latest stemcell of this series to the target gallery."""
        raise NotImplementedError
