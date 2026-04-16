---
trigger: always_on
---
---
trigger: always_on
---

# Qoder 项目规则

## Python 环境要求

- **必须使用本地虚拟环境**，如 `.venv`
- 所有 Python 项目必须在虚拟环境中运行
- 不允许使用全局 Python 环境

## 虚拟环境设置

### 创建虚拟环境
python -m venv .venv

### 激活虚拟环境
- Windows:
  .venv\Scripts\activate
- Linux/Mac:
  source .venv/bin/activate

### 安装依赖
pip install -r requirements.txt

## 最佳实践

1. 在项目根目录创建 `.venv` 文件夹
2. 将 `.venv` 添加到 `.gitignore`
3. 使用 `requirements.txt` 管理依赖
4. 确保所有团队成员使用相同的虚拟环境配置



## Code Quality Standards

### Comment Language
- All code comments MUST be written in English
- Exception: User-facing documentation can be in Chinese
- Keep comments clear, concise and professional

### Code Style
- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Keep functions focused and modular
- Maximum line length: 88 characters (Black formatter standard)

### Documentation
- Add docstrings for all public functions and classes
- Use type hints for function parameters and return values
- Include example usage in docstrings when appropriate

### Version Control
- Write clear, descriptive commit messages in English
- Use conventional commits format: `type(scope): description`
- Types: feat, fix, docs, style, refactor, test, chore

## Testing Requirements

### Unit Tests
- Write unit tests for all new features
- Maintain minimum 80% code coverage
- Use `pytest` as the testing framework
- Place tests in `tests/` directory

### Running Tests
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_example.py

## Dependencies Management

### Adding New Dependencies
1. Install in virtual environment: `pip install package-name`
2. Update requirements: `pip freeze > requirements.txt`
3. Document why the dependency is needed
4. Keep dependencies minimal and up-to-date

### Security
- Regularly update dependencies: `pip list --outdated`
- Check for vulnerabilities: `pip-audit`
- Pin critical dependencies to specific versions



## AI Collaboration Guidelines

### Discussion Mode
- When user says "讨论下" (let's discuss), "聊聊" (let's chat), or similar conversational phrases, enter discussion mode
- In discussion mode: DO NOT modify any code
- Focus on explaining, clarifying, and exploring ideas through conversation
- Only generate or modify code when explicitly asked with clear action words like:
  - "修改" (modify)
  - "添加" (add)
  - "创建" (create)
  - "实现" (implement)
  - "生成" (generate)

### Code Generation Rules
- Always wait for explicit instruction before writing code
- Confirm understanding before making changes
- Explain the changes you plan to make before implementing them
- Ask for clarification if requirements are ambiguous

### Response Language
- Use Chinese for explanations and discussions with users
- Use English for code comments (as per Code Quality Standards)
- Maintain professional and friendly tone in all interactions


### Adding New Dependencies
- **Never hardcode API keys or secrets in code**
- All sensitive information must be stored in configuration files (e.g., `.env`)
- Use environment variables to access API keys: `os.getenv('API_KEY')`
- Add `.env` to `.gitignore` to prevent accidental commits
- Provide `.env.example` template with dummy values for team reference



## Development Workflow

### Temporary Test Scripts
- All temporary test scripts and experimental code must be placed in the `playground/` directory
- Create the `playground/` directory at project root if it doesn't exist
- Add `playground/` to `.gitignore` to prevent committing temporary code
- Keep production code separate from experimental code

#### Setup
# Create playground directory
mkdir playground

# Add to .gitignore
echo "playground/" >> .gitignore

### Playground Usage
- Use for quick prototypes and experiments
- Test new features before integrating into main codebase
- Try different approaches without affecting production code
- Clean up or move successful experiments to proper project structure




## Dependencies Management

### Updating Dependencies
- When adding new dependencies, update the appropriate dependency file:
  - If `pyproject.toml` exists, add the dependency there
  - If `requirements.txt` exists, update it with `pip freeze > requirements.txt`
  - If both exist, prioritize `pyproject.toml` and ensure consistency
- Always test that the updated dependency file works correctly
- Document any version constraints and reasons for them

### pyproject.toml (if using)
# Add dependencies under [project.dependencies]
[project.dependencies]
requests = ">=2.28.0"

# Add development dependencies under [project.optional-dependencies]
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "black>=22.0.0",
]

### requirements.txt (if using)
# Update after installing new packages
pip freeze > requirements.txt

# Or manually add with version pinning
requests==2.28.2
pytest==7.2.0



## Documentation Guidelines

### When to Write Documentation
- **Only write documentation when explicitly requested by the user**
- Do not automatically create documentation after completing a task
- Focus on implementing functionality first
- Documentation should be created separately and intentionally

### Documentation Types
- API documentation: Only when user asks for API docs
- User guides: Only when user requests user documentation
- Technical specs: Only when explicitly needed
- README updates: Only when user asks to update README

### Documentation Process
1. Complete the implementation task
2. Wait for user's explicit request for documentation
3. Ask user what type of documentation they need
4. Create targeted documentation based on specific requirements

### Exception
- Inline code comments are always required (as per Code Quality Standards)
- Docstrings for functions/classes are mandatory
- These are part of code quality, not separate documentation tasks
