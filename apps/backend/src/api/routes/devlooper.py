import asyncio

from typing import Callable, List

import modal


@dataclass
class EnvTemplate:
    # Base Modal image.
    image: modal.Image
    # Command to run to test the project.
    test_cmd: str
    # Working directory of the project. The LLM-generated code will be mounted here.
    workdir: str
    # Template-specific prompt to be appended to the user's input prompt.
    prompt: str
    # Function to extend the image and install packages in it.
    install_packages: Callable[[modal.Image, List[str]], modal.Image
    # Package manager used by the template.
    package_manager: str


TEMPLATES = {
    "python": EnvTemplate(
        test_cmd="python -m pytest . -x",
        workdir="/app",
        image=modal.Image.debian_slim().pip_install("pytest"),
        install_packages=lambda image, packages: image.pip_install(packages),
        package_manager="pip",
        prompt="""The project must be in Python, and have tests.

                Assume you have the following file structure:
                    - setup.py
                    - test/
                    - app/

                You just have to populate app/ and test/. """,
    ),
    "rust": EnvTemplate(
        test_cmd="cargo test",
        workdir="/app",
        image=(
            modal.Image.from_registry("rust:slim")
            .apt_install("build-essential")
            .run_commands("cargo new app --bin")
            .workdir("/app")
        ),
        install_packages=lambda image, packages: image.run_commands(f"cargo add {' '.join(packages)}"),
        package_manager="cargo",
        prompt="""The project must be in Rust, and have tests.

                Assume you have the following file structure:
                    - Cargo.toml
                    - src/
                    - tests/

                You just have to populate src/ and tests/. DO NOT generate Cargo.toml.""",
    ),
    "react": EnvTemplate(
        test_cmd="yarn run jest --bail",
        workdir="/app",
        image=(
            modal.Image.from_registry("node:slim")
            .run_commands("yarn create vite app --template react")
            .workdir("/app")
            .run_commands(
                "yarn add --dev jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom",
                "yarn add --dev babel-jest @babel/core @babel/preset-env @babel/preset-react",
            )
            .run_commands(
                """echo '{ "presets": [ "@babel/preset-env", ["@babel/preset-react", {runtime: "automatic"}] ] }' > babel.config.json""",
                """echo '{ "testEnvironment": "jsdom" }' > jest.config.json""",
            )
        ),
        install_packages=lambda image, packages: image.run_commands(f"yarn add {' '.join(packages)}"),
        package_manager="yarn",
        prompt="""The project must be in React, and have tests.

                Assume you have a new create-react-app project already set up with the following files:
                    - index.html
                    - package.json
                    - src/

                You just have to populate src/. Please use the .jsx extension for files with JSX.""",
    ),
}

import difflib

from colorama import Fore


def print_diff(original: str, modified: str):
    diff = difflib.ndiff(original.splitlines(), modified.splitlines())
    for line in diff:
        if line.startswith("-"):
            print(Fore.RED + line + Fore.RESET)
        elif line.startswith("+"):
            print(Fore.GREEN + line + Fore.RESET)


def print_info(info: str):
    print(Fore.WHITE + info + Fore.RESET)


def print_section_header(header: str):
    print(Fore.MAGENTA + f"\n======= {header} =======\n" + Fore.RESET)

import enum
import logging
from dataclasses import dataclass
from typing import List

import openai
from openai_function_call import OpenAISchema
from pydantic import Field
from smol_dev.prompts import SMOL_DEV_SYSTEM_PROMPT
from tenacity import (
    after_log,
    retry,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)

retry_dec = retry(
    wait=wait_random_exponential(min=5, max=120),
    stop=stop_after_attempt(8),
    after=after_log(logger, logging.WARN),
)


@retry_dec
def debug_code(
    prompt: str,
    current_file_content: str,
    current_file_path: str,
    file_paths: List[str],
    diagnosis: str,
    model: str,
) -> str:
    # Not using OpenAI schema here because of JSON decoding issues.

    completion = openai.ChatCompletion.create(
        model=model,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": f"""{SMOL_DEV_SYSTEM_PROMPT}

    You will be given a user's prompt for a program they want, the output of tests that were run on the program, and a possible diagnosis of the issue.

    Given this information, and one of the files, determine if the file is the source of the bug, and if so, fix it.

    If the file is the source of the bug, output the fixed code. Otherwise, output the string `None` and NOTHING ELSE.

    Only write valid code for the given filepath and file type, and return only the code. *DO NOT* include comments explaining what the bug was, or add any other explanation.""",
            },
            {
                "role": "user",
                "content": f""" I want a: {prompt} """,
            },
            {
                "role": "user",
                "content": f""" The full list of file paths is {file_paths}. The path of the current file is {current_file_path}. Its contents are: {current_file_content} """,
            },
            {
                "role": "user",
                "content": f""" A likely diagnosis for the bug is: {diagnosis} """,
            },
            {
                "role": "user",
                "content": """ - MOST IMPORTANT OF ALL every line of code you generate must be valid code. Do not include code fences in your response, for example

    Bad response (because it contains the code fence):
    ```javascript
    console.log("hello world")
    ```

    Good response (because it only contains the code):
    console.log("hello world")

    Begin generating the code now. """,
            },
        ],
    )
    text = completion.choices[0].message.content
    if text.endswith("None"):
        return current_file_content
    return text


class PackagesNeeded(OpenAISchema):
    """A list of packages needed."""

    packages: List[str]


@retry_dec
def initial_packages_needed(prompt: str, plan: str, package_manager: str, model: str):
    completion = openai.ChatCompletion.create(
        model=model,
        temperature=0.7,
        functions=[PackagesNeeded.openai_schema],
        function_call={"name": "PackagesNeeded"},
        messages=[
            {
                "role": "system",
                "content": f"""{SMOL_DEV_SYSTEM_PROMPT}

    When given their intent, create a list of packages installable via {package_manager} that the user would want to install for the program.

    Do not include packages part of the standard library already.

    Do not add any other explanation, only return a list of strings.
                """,
            },
            {
                "role": "user",
                "content": f""" I want a: {prompt} """,
            },
            {
                "role": "user",
                "content": f""" The plan we have agreed on is: {plan} """,
            },
        ],
    )
    return PackagesNeeded.from_response(completion).packages


@retry_dec
def diagnose_issue(
    prompt: str,
    plan: str,
    file_paths: List[str],
    test_command: str,
    test_stdout: str,
    test_stderr: str,
    model: str,
) -> str:
    completion = openai.ChatCompletion.create(
        model=model,
        temperature=0.7,
        messages=[
            {
                "role": "system",
                "content": f"""{SMOL_DEV_SYSTEM_PROMPT}

        You will be given a user's prompt for a program they want, and the output of tests that were run on the program.
`
        Given this information, and a list of the file paths, come up with a short diagnosis of what the issue is. Along with each suggested change, include the file path that the change should be made in.

        You may also suggest packages that should be installed or changes to the environment that should be made.

        Do not provide any general advice that does not fix these issues. """,
            },
            {
                "role": "user",
                "content": f""" I want a: {prompt} """,
            },
            {
                "role": "user",
                "content": f""" The plan we have agreed on is: {plan} """,
            },
            {
                "role": "user",
                "content": f""" The full list of file paths is {file_paths}.""",
            },
            {
                "role": "user",
                "content": f""" After running {test_command}, the stdout was: {test_stdout} """,
            },
            {
                "role": "user",
                "content": f""" After running {test_command}, the stderr was: {test_stderr} """,
            },
        ],
    )

    return completion.choices[0].message.content


@dataclass
class DebugPlan:
    debug_file_paths: List[str]
    install_packages: List[str]
    run_commands: List[str]


@retry_dec
def plan_debug_actions(
    prompt: str,
    package_manager: str,
    file_paths: List[str],
    diagnosis: str,
    model: str,
) -> DebugPlan:
    FilePath = enum.Enum("FilePaths", {path: path for path in file_paths})

    # Create another class so it has the right enum values.
    class _DebugPlan(OpenAISchema):
        """A plan to fix the given bugs in the program."""

        debug_file_paths: List[FilePath] = Field(..., description="The file paths to debug.")
        install_packages: List[str] = Field(..., description="The packages to install.")
        run_commands: List[str] = Field(..., description="Bash commands to run during image build.")

    completion = openai.ChatCompletion.create(
        model=model,
        temperature=0.7,
        functions=[_DebugPlan.openai_schema],
        function_call={"name": "_DebugPlan"},
        messages=[
            {
                "role": "system",
                "content": f"""{SMOL_DEV_SYSTEM_PROMPT}

    You will be given a user's prompt for a program they want, the output of tests that were run on the program, and a diagnosis for the issue.

    Given this information, and a list of the file paths, output:

    1. Any files that need to be corrected

    2. Any packages that needs to be installed in the environment via {package_manager}. Do not reinstall packages that are already installed.

    3. Any commands that need to be run (e.g. `apt-get install -y pkg-config`). Note that the OS is Debian-based. Do not use sudo in the command.

    *DO NOT* add any other explanation.""",
            },
            {
                "role": "user",
                "content": f""" I want a: {prompt} """,
            },
            {
                "role": "user",
                "content": f""" The full list of file paths is {file_paths}.""",
            },
            {
                "role": "user",
                "content": f""" A likely diagnosis for the bug is: {diagnosis} """,
            },
        ],
    )

    _plan = _DebugPlan.from_response(completion)
    return DebugPlan(
        debug_file_paths=[fp.value for fp in _plan.debug_file_paths],
        install_packages=_plan.install_packages,
        run_commands=_plan.run_commands,
    )


import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Tuple

import modal

from env_templates import TEMPLATES, EnvTemplate

MAX_CONCURRENT_GENERATIONS = 3


@dataclass
class State:
    input_prompt: str
    code: Dict[str, str]
    package_layers: List[List[str]]
    run_commands: List[List[str]]

    def prompt(self) -> str:
        packages: List[str] = sum(self.package_layers, [])
        return f"{self.input_prompt}\n\nAssume you have these packages installed: {packages}"


app = modal.App("devlooper")

devlooper_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("git+https://github.com/smol-ai/developer.git")
    .pip_install("colorama")
)


def write_files(code: Dict[str, str], dir: Path):
    for file_path, contents in code.items():
        p = dir / file_path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            f.write(contents)


def run_in_sandbox(state: State, template: EnvTemplate) -> Tuple[int, str, str]:
    local_dir = Path(TemporaryDirectory().name)
    write_files(state.code, local_dir)

    image = template.image

    # TODO: install packages and run commands in the right order (maybe just build an image object incrementally
    # in the state?)
    for commands in state.run_commands:
        image = image.run_commands(*commands)

    # Install package lists in stages (so that previously installed layers don't get rebuilt)
    for package_list in state.package_layers:
        image = template.install_packages(image, package_list)

    sb = modal.Sandbox.create(
        "bash",
        "-c",
        template.test_cmd,
        image=image,
        mounts=[
            modal.Mount.from_local_dir(
                local_dir,
                remote_path=template.workdir,
            )
        ],
        timeout=120,
        workdir=template.workdir,
    )

    sb.wait()

    return (sb.returncode, sb.stdout.read(), sb.stderr.read())


@app.function(
    image=devlooper_image,
    secrets=[modal.Secret.from_name("openai-secret")],
    timeout=30 * 60,  # 30 minutes
)
async def devlooper(input_prompt: str, template_name: str, model: str = "gpt-4-1106-preview") -> State:
    from smol_dev.prompts import generate_code, plan, specify_file_paths

    from .display import print_diff, print_info, print_section_header
    from .prompts import (
        debug_code,
        diagnose_issue,
        initial_packages_needed,
        plan_debug_actions,
    )

    try:
        template = TEMPLATES[template_name]
    except KeyError:
        raise ValueError(f"Unknown template name {template_name}. Must be one of {TEMPLATES.keys()}")

    input_prompt = f"{input_prompt}\n{template.prompt}"

    print_section_header("Generating initial plan...")
    current_plan = plan(input_prompt, model=model)
    print(current_plan)

    print_section_header("Generating initial packages...")
    initial_packages = initial_packages_needed(input_prompt, current_plan, template.package_manager, model=model)
    print(initial_packages)

    state = State(input_prompt=input_prompt, code={}, package_layers=[initial_packages], run_commands=[])

    print_section_header("Generating file paths...")
    file_paths = specify_file_paths(state.prompt(), current_plan, model=model)
    print(file_paths)

    # OpenAI rate limits make this necessary.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)

    async def gen(file_path):
        async with semaphore:
            return file_path, await generate_code(state.prompt(), current_plan, file_path, model=model)

    coros = [gen(file_path) for file_path in file_paths]
    state.code = dict(await asyncio.gather(*coros))

    i = 0
    yield i, state
    returncode, stdout, stderr = run_in_sandbox(state, template)

    while returncode != 0:
        i += 1
        print_section_header(f"Iteration {i}")

        diagnosis = diagnose_issue(
            state.prompt(),
            current_plan,
            file_paths,
            template.test_cmd,
            stdout,
            stderr,
            model=model,
        )
        print(diagnosis)

        actions = plan_debug_actions(
            state.prompt(),
            template.package_manager,
            file_paths,
            diagnosis,
            model=model,
        )

        if actions.install_packages:
            print_info(f"Installing packages {actions.install_packages}.")
            state.package_layers.append(actions.install_packages)

        if actions.run_commands:
            print_info(f"Running commands {actions.run_commands}.")
            state.run_commands.append(actions.run_commands)

        for file_path in actions.debug_file_paths:
            print_info(f"Debugging {file_path}...")

            original_code = state.code[file_path]

            updated_code = debug_code(
                state.prompt(),
                original_code,
                file_path,
                file_paths,
                diagnosis,
                model=model,
            )

            if updated_code != original_code:
                print_diff(original_code, updated_code)
                state.code[file_path] = updated_code
            else:
                print("No changes made.")

        yield i, state
        returncode, stdout, stderr = run_in_sandbox(state, template)

    print_section_header("Success!")


@app.local_entrypoint()
def main(
    prompt: str = "Create a Tic-Tac-Toe game.",
    template: str = "react",
    output_path: str = "output",
):
    for i, state in devlooper.remote_gen(prompt, template):
        path = Path(output_path) / app.app_id / str(i)

        print("Writing files to", path.absolute())
        write_files(state.code, path)

        print(f"Packages: {state.package_layers}")
        print(f"Image commands: {state.run_commands}")

def generate_prompt(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"


def generate_code(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"


def generate_file_paths(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"


def generate_diagnosis(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"


def generate_debug_actions(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"


def generate_debug_code(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"

def generate_debug_file_paths(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"

def generate_debug_diagnosis(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"

def generate_debug_debug_actions(prompt: str, template: str) -> str:
    return f"{prompt}\n\nAssume you have these packages installed: {template.initial_packages}"
