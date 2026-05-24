"""
tests/test_stack_detector.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for analyzers/stack_detector.py

Run with:
    pytest tests/test_stack_detector.py -v
"""

from __future__ import annotations

import sys
import pathlib

# Make the project root importable when running pytest from the project dir
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import asyncio
import pytest

from analyzers.stack_detector import (
    StackResult,
    detect_stack,
    detect_stack_sync,
    _detect_languages,
    _detect_frameworks,
    _detect_databases,
    _detect_infra,
    _detect_test_frameworks,
    _detect_package_manager,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def run(coro):
    """Run a coroutine in a fresh event loop (compatible with all pytest versions)."""
    return asyncio.run(coro)


# ──────────────────────────────────────────────────────────────────────────────
# StackResult model
# ──────────────────────────────────────────────────────────────────────────────


class TestStackResult:
    def test_defaults_are_empty(self):
        r = StackResult()
        assert r.languages == []
        assert r.frameworks == []
        assert r.databases == []
        assert r.infra == []
        assert r.test_frameworks == []
        assert r.package_manager is None

    def test_model_is_serialisable(self):
        r = StackResult(languages=["Python"], package_manager="pip")
        d = r.model_dump()
        assert d["languages"] == ["Python"]
        assert d["package_manager"] == "pip"


# ──────────────────────────────────────────────────────────────────────────────
# Language detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectLanguages:
    def test_python_files(self):
        paths = ["main.py", "core/config.py", "tests/test_foo.py"]
        assert "Python" in _detect_languages(paths)

    def test_js_and_ts_map_to_same_label(self):
        paths = ["index.js", "src/app.ts", "utils.js"]
        langs = _detect_languages(paths)
        assert "JavaScript/TypeScript" in langs

    def test_go_files(self):
        assert "Go" in _detect_languages(["main.go", "server.go"])

    def test_rust_files(self):
        assert "Rust" in _detect_languages(["src/main.rs", "lib.rs"])

    def test_java_files(self):
        assert "Java" in _detect_languages(["App.java", "Service.java"])

    def test_ruby_files(self):
        assert "Ruby" in _detect_languages(["app.rb"])

    def test_csharp_files(self):
        assert "C#" in _detect_languages(["Program.cs"])

    def test_php_files(self):
        assert "PHP" in _detect_languages(["index.php"])

    def test_unknown_extensions_ignored(self):
        langs = _detect_languages(["README.md", ".gitignore", "Makefile"])
        assert langs == []

    def test_dominant_language_is_first(self):
        # 3 Python files vs 1 Go file → Python should come first
        paths = ["a.py", "b.py", "c.py", "main.go"]
        langs = _detect_languages(paths)
        assert langs[0] == "Python"

    def test_empty_input(self):
        assert _detect_languages([]) == []


# ──────────────────────────────────────────────────────────────────────────────
# Framework detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectFrameworks:
    # ── Next.js ──────────────────────────────────────────────────────────────
    def test_nextjs(self):
        contents = {"package.json": '{"dependencies": {"next": "14.0.0", "react": "18"}}'}
        assert "Next.js" in _detect_frameworks(contents)

    def test_nextjs_not_react_too(self):
        """When Next.js is detected, React must NOT appear separately."""
        contents = {"package.json": '{"dependencies": {"next": "14.0.0", "react": "18"}}'}
        fw = _detect_frameworks(contents)
        assert "React" not in fw

    # ── React (without Next) ─────────────────────────────────────────────────
    def test_react_without_next(self):
        contents = {"package.json": '{"dependencies": {"react": "18.0.0"}}'}
        fw = _detect_frameworks(contents)
        assert "React" in fw
        assert "Next.js" not in fw

    # ── Express / Fastify ─────────────────────────────────────────────────────
    def test_express(self):
        contents = {"package.json": '{"dependencies": {"express": "4.18.0"}}'}
        assert "Express" in _detect_frameworks(contents)

    def test_fastify(self):
        contents = {"package.json": '{"dependencies": {"fastify": "4.0.0"}}'}
        assert "Fastify" in _detect_frameworks(contents)

    # ── Python ────────────────────────────────────────────────────────────────
    def test_fastapi(self):
        contents = {"requirements.txt": "fastapi==0.111.0\nuvicorn\n"}
        assert "FastAPI" in _detect_frameworks(contents)

    def test_django(self):
        contents = {"requirements.txt": "Django==4.2\n"}
        assert "Django" in _detect_frameworks(contents)

    def test_flask(self):
        contents = {"requirements.txt": "flask==3.0\n"}
        assert "Flask" in _detect_frameworks(contents)

    # ── Java ─────────────────────────────────────────────────────────────────
    def test_spring_boot(self):
        contents = {"pom.xml": "<artifactId>spring-boot-starter-web</artifactId>"}
        assert "Spring Boot" in _detect_frameworks(contents)

    # ── Go ───────────────────────────────────────────────────────────────────
    def test_gin(self):
        contents = {"go.mod": "require github.com/gin-gonic/gin v1.9.1"}
        assert "Gin" in _detect_frameworks(contents)

    def test_fiber(self):
        contents = {"go.mod": "require github.com/gofiber/fiber/v2 v2.52.0"}
        assert "Fiber" in _detect_frameworks(contents)

    def test_no_framework_detected(self):
        contents = {"package.json": '{"dependencies": {"lodash": "4.17.21"}}'}
        assert _detect_frameworks(contents) == []

    def test_empty_contents(self):
        assert _detect_frameworks({}) == []


# ──────────────────────────────────────────────────────────────────────────────
# Database detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectDatabases:
    def test_sqlalchemy_implies_postgresql(self):
        contents = {"requirements.txt": "sqlalchemy==2.0\n"}
        assert "PostgreSQL" in _detect_databases([], contents)

    def test_psycopg_implies_postgresql(self):
        contents = {"requirements.txt": "psycopg2-binary==2.9\n"}
        assert "PostgreSQL" in _detect_databases([], contents)

    def test_pymongo(self):
        contents = {"requirements.txt": "pymongo==4.6\n"}
        assert "MongoDB" in _detect_databases([], contents)

    def test_redis(self):
        contents = {"requirements.txt": "redis==5.0\n"}
        assert "Redis" in _detect_databases([], contents)

    def test_mongoose(self):
        contents = {"package.json": '{"dependencies": {"mongoose": "8.0.0"}}'}
        assert "MongoDB" in _detect_databases([], contents)

    def test_prisma_defaults_to_postgresql(self):
        contents = {"package.json": '{"dependencies": {"prisma": "5.0.0"}}'}
        assert "PostgreSQL" in _detect_databases([], contents)

    def test_prisma_confirmed_by_schema(self):
        contents = {
            "package.json": '{"dependencies": {"prisma": "5.0.0"}}',
            "schema.prisma": 'datasource db { provider = "postgresql" }',
        }
        assert "PostgreSQL" in _detect_databases([], contents)

    def test_compose_mysql(self):
        contents = {"docker-compose.yml": "services:\n  db:\n    image: mysql:8\n"}
        assert "MySQL" in _detect_databases([], contents)

    def test_compose_postgres(self):
        contents = {"docker-compose.yml": "services:\n  db:\n    image: postgres:16\n"}
        assert "PostgreSQL" in _detect_databases([], contents)

    def test_no_duplicates_when_detected_twice(self):
        """SQLAlchemy + docker-compose both hint PostgreSQL → only one entry."""
        contents = {
            "requirements.txt": "sqlalchemy\n",
            "docker-compose.yml": "image: postgres:16\n",
        }
        dbs = _detect_databases([], contents)
        assert dbs.count("PostgreSQL") == 1

    def test_empty(self):
        assert _detect_databases([], {}) == []


# ──────────────────────────────────────────────────────────────────────────────
# Infrastructure detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectInfra:
    def test_dockerfile(self):
        assert "Docker" in _detect_infra(["Dockerfile", "main.py"])

    def test_dockerfile_case_insensitive_basename(self):
        assert "Docker" in _detect_infra(["backend/Dockerfile"])

    def test_docker_compose_yml(self):
        assert "Docker Compose" in _detect_infra(["docker-compose.yml"])

    def test_docker_compose_yaml(self):
        assert "Docker Compose" in _detect_infra(["docker-compose.yaml"])

    def test_github_actions(self):
        paths = [".github/workflows/ci.yml", "main.py"]
        assert "GitHub Actions" in _detect_infra(paths)

    def test_github_actions_nested(self):
        paths = [".github/workflows/release.yaml"]
        assert "GitHub Actions" in _detect_infra(paths)

    def test_kubernetes_dir(self):
        paths = ["kubernetes/deployment.yaml", "kubernetes/service.yaml"]
        assert "Kubernetes" in _detect_infra(paths)

    def test_k8s_shorthand(self):
        paths = ["k8s/deployment.yaml"]
        assert "Kubernetes" in _detect_infra(paths)

    def test_terraform(self):
        paths = ["terraform/main.tf", "terraform/variables.tf"]
        assert "Terraform" in _detect_infra(paths)

    def test_no_infra(self):
        assert _detect_infra(["main.py", "README.md"]) == []

    def test_empty(self):
        assert _detect_infra([]) == []


# ──────────────────────────────────────────────────────────────────────────────
# Test framework detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectTestFrameworks:
    def test_pytest(self):
        contents = {"requirements.txt": "pytest==8.0\npytest-asyncio\n"}
        assert "pytest" in _detect_test_frameworks(contents)

    def test_jest(self):
        contents = {"package.json": '{"devDependencies": {"jest": "29.0.0"}}'}
        assert "Jest" in _detect_test_frameworks(contents)

    def test_vitest(self):
        contents = {"package.json": '{"devDependencies": {"vitest": "1.0.0"}}'}
        assert "Vitest" in _detect_test_frameworks(contents)

    def test_all_three(self):
        contents = {
            "requirements.txt": "pytest\n",
            "package.json": '{"devDependencies": {"jest": "29", "vitest": "1"}}',
        }
        tf = _detect_test_frameworks(contents)
        assert set(tf) == {"pytest", "Jest", "Vitest"}

    def test_none(self):
        assert _detect_test_frameworks({}) == []


# ──────────────────────────────────────────────────────────────────────────────
# Package manager detection
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectPackageManager:
    def test_poetry(self):
        assert _detect_package_manager(["poetry.lock", "pyproject.toml"], {}) == "poetry"

    def test_pipenv(self):
        assert _detect_package_manager(["Pipfile.lock"], {}) == "pipenv"

    def test_pip_via_requirements(self):
        assert _detect_package_manager(["requirements.txt"], {}) == "pip"

    def test_pip_via_pyproject(self):
        assert _detect_package_manager(["pyproject.toml"], {}) == "pip"

    def test_pnpm(self):
        assert _detect_package_manager(["pnpm-lock.yaml", "package.json"], {}) == "pnpm"

    def test_yarn(self):
        assert _detect_package_manager(["yarn.lock", "package.json"], {}) == "yarn"

    def test_npm_via_lock(self):
        assert _detect_package_manager(["package-lock.json", "package.json"], {}) == "npm"

    def test_npm_via_package_json(self):
        assert _detect_package_manager(["package.json"], {}) == "npm"

    def test_go_modules(self):
        assert _detect_package_manager(["go.mod", "go.sum"], {}) == "go modules"

    def test_cargo(self):
        assert _detect_package_manager(["Cargo.toml", "Cargo.lock"], {}) == "cargo"

    def test_bundler(self):
        assert _detect_package_manager(["Gemfile", "Gemfile.lock"], {}) == "bundler"

    def test_poetry_beats_pip(self):
        """poetry.lock present alongside requirements.txt → poetry wins."""
        assert _detect_package_manager(["poetry.lock", "requirements.txt"], {}) == "poetry"

    def test_none(self):
        assert _detect_package_manager([], {}) is None


# ──────────────────────────────────────────────────────────────────────────────
# Full async pipeline — integration-style tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDetectStack:
    """End-to-end tests exercising the public async entry point."""

    def test_python_fastapi_project(self):
        paths = [
            "main.py",
            "core/config.py",
            "tests/test_main.py",
            "requirements.txt",
            "Dockerfile",
            ".github/workflows/ci.yml",
        ]
        contents = {
            "requirements.txt": "fastapi==0.111.0\nuvicorn\nsqlalchemy\npytest\n",
        }
        result = run(detect_stack(paths, contents))

        assert "Python" in result.languages
        assert "FastAPI" in result.frameworks
        assert "PostgreSQL" in result.databases
        assert "Docker" in result.infra
        assert "GitHub Actions" in result.infra
        assert "pytest" in result.test_frameworks
        assert result.package_manager == "pip"

    def test_nextjs_project(self):
        paths = [
            "pages/index.tsx",
            "package.json",
            "package-lock.json",
            "Dockerfile",
            "docker-compose.yml",
            "k8s/deployment.yaml",
        ]
        contents = {
            "package.json": (
                '{"dependencies": {"next": "14", "react": "18"},'
                ' "devDependencies": {"jest": "29"}}'
            ),
            "docker-compose.yml": "services:\n  db:\n    image: postgres:16\n",
        }
        result = run(detect_stack(paths, contents))

        assert "JavaScript/TypeScript" in result.languages
        assert "Next.js" in result.frameworks
        assert "React" not in result.frameworks
        assert "PostgreSQL" in result.databases
        assert "Docker" in result.infra
        assert "Docker Compose" in result.infra
        assert "Kubernetes" in result.infra
        assert "Jest" in result.test_frameworks
        assert result.package_manager == "npm"

    def test_go_microservice(self):
        paths = ["main.go", "handler.go", "go.mod", "go.sum", "terraform/main.tf"]
        contents = {
            "go.mod": "module myapp\n\nrequire github.com/gin-gonic/gin v1.9.1\n",
        }
        result = run(detect_stack(paths, contents))

        assert "Go" in result.languages
        assert "Gin" in result.frameworks
        assert "Terraform" in result.infra
        assert result.package_manager == "go modules"

    def test_empty_repo(self):
        result = run(detect_stack([], {}))
        assert result == StackResult()

    def test_returns_stack_result_instance(self):
        result = run(detect_stack(["main.py"], {"requirements.txt": "fastapi\n"}))
        assert isinstance(result, StackResult)

    def test_sync_wrapper_returns_same_as_async(self):
        paths = ["main.py"]
        contents = {"requirements.txt": "fastapi\npytest\n"}
        async_result = run(detect_stack(paths, contents))
        sync_result = detect_stack_sync(paths, contents)
        assert async_result == sync_result

    def test_nested_key_file_paths(self):
        """file_contents keyed with subdirectory paths should still be matched."""
        paths = ["backend/requirements.txt", "backend/main.py"]
        contents = {"backend/requirements.txt": "django\npytest\n"}
        result = run(detect_stack(paths, contents))
        assert "Django" in result.frameworks
        assert "pytest" in result.test_frameworks

    def test_no_duplicates_in_any_field(self):
        """Multiple signals for the same item must not produce duplicates."""
        paths = ["docker-compose.yml"]
        contents = {
            "requirements.txt": "psycopg2\nsqlalchemy\n",
            "docker-compose.yml": "image: postgres:16",
        }
        result = run(detect_stack(paths, contents))
        assert result.databases.count("PostgreSQL") == 1


# ──────────────────────────────────────────────────────────────────────────────
# Edge / boundary cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_case_insensitive_file_content(self):
        """Package names might appear in mixed case in requirements."""
        contents = {"requirements.txt": "FastAPI==0.111.0\nSQLAlchemy>=2\nPytest\n"}
        result = run(detect_stack([], contents))
        assert "FastAPI" in result.frameworks
        assert "PostgreSQL" in result.databases
        assert "pytest" in result.test_frameworks

    def test_partial_word_does_not_match(self):
        """'nextcloud' in package.json must not trigger Next.js."""
        # Our rule checks for the JSON string `"next"` (with quotes in lowered content)
        contents = {"package.json": '{"dependencies": {"nextcloud-client": "1.0"}}'}
        fw = _detect_frameworks(contents)
        assert "Next.js" not in fw

    def test_windows_style_paths_normalised(self):
        """Backslash paths (Windows) should still match infra rules."""
        paths = [r".github\workflows\ci.yml", r"kubernetes\deployment.yaml"]
        infra = _detect_infra(paths)
        assert "GitHub Actions" in infra
        assert "Kubernetes" in infra

    def test_multiple_python_frameworks(self):
        """Requirements can legitimately list multiple frameworks (e.g. monorepo)."""
        contents = {"requirements.txt": "fastapi\nflask\ndjango\n"}
        fw = _detect_frameworks(contents)
        assert "FastAPI" in fw
        assert "Flask" in fw
        assert "Django" in fw
