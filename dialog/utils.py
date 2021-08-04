from inspect import getfullargspec, FullArgSpec
from typing import Callable, Any, TypeVar, Union
from typing import Coroutine


T = TypeVar('T')


async def run_function(function: Union[Callable[..., Coroutine[Any, Any, T]],
                                       Callable[..., T]],
                       *args, **kwargs) -> T:
    try:
        function_spec: FullArgSpec = function.full_arg_spec  # NOQA
    except AttributeError:
        function_spec = getfullargspec(getattr(function, '__wrapped__', function))
        function.__dict__['full_arg_spec'] = function_spec

    if function_spec.varargs:
        function_args = args
    else:
        function_args = args[:len(function_spec.args)]

    function_kwargs = check_spec(function_spec, kwargs)

    result = function(*function_args, **function_kwargs)
    if isinstance(result, Coroutine):
        result = await result

    return result


def check_spec(spec: FullArgSpec, kwargs: dict) -> dict:
    if spec.varkw:
        return kwargs

    return {k: v for k, v in kwargs.items() if k in set(spec.args + spec.kwonlyargs)}


def is_url(string: str) -> bool:
    if ":" not in string:
        return False

    scheme = string.split(":", 1)[0].lower()

    return scheme in [
        "http",
        "https",
        "file",
        "ftp",
        "ssh",
        "git",
        "hg",
        "bzr",
        "sftp",
        "svn",
        "ssh",
    ]
