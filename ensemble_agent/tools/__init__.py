"""Tool provider registry and loader."""

from .base import ToolProvider
from .file_ops import FileOpsTools
from .runner import RunnerTools
from .generator import GeneratorTools
# from .reference_loader import ReferenceLoader


def load_tool_providers(config, archive):
    """Load tool providers based on config.

    Always loads: file_ops, runner.
    Loads generator only when not using existing scripts.
    """
    providers = [
        FileOpsTools(config, archive),
        RunnerTools(config, archive),
        # ReferenceLoader(config, archive),
    ]
    if not config.scripts_dir:
        providers.append(GeneratorTools(config, archive))
    return providers
