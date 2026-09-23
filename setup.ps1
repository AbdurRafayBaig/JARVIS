<#>
.SYNOPSIS
    JARVIS Setup Script - Installs dependencies and configures the environment
.DESCRIPTION
    This script sets up the JARVIS development environment:
    - Checks Python version
    - Creates virtual environment
    - Installs dependencies
    - Creates .env from .env.example
    - Validates configuration
    - Runs basic diagnostics
.PARAMETER Dev
    Install development dependencies (testing, linting, etc.)
.PARAMETER Force
    Force reinstall even if already installed
.PARAMETER NoVenv
    Skip virtual environment creation (use system Python)
.EXAMPLE
    .\setup.ps1
.EXAMPLE
    .\setup.ps1 -Dev
.EXAMPLE
    .\setup.ps1 -Force
#>

[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Force,
    [switch]$NoVenv
)

$ErrorActionPreference = "Stop"

# Colors - using Write-Host foreground colors instead of ANSI
function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "  [ERR] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host ""
}

# Header
Write-Header "JARVIS SETUP - Personal AI Computer Agent for Windows"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Not running as Administrator. Some features may require admin rights."
}

# Check Python
Write-Step "Checking Python installation..."
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found in PATH. Please install Python 3.11+"
    exit 1
}
Write-Success "Found: $pythonVersion"

# Check version
$versionParts = ($pythonVersion -split ' ')[1] -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
    Write-Error "Python 3.11+ required. Found $major.$minor"
    exit 1
}
Write-Success "Python version OK (3.11+)"

# Check pip
Write-Step "Checking pip..."
pip --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip not found"
    exit 1
}
Write-Success "pip available"

# Virtual environment
$venvPath = ".\.venv"
if (-not $NoVenv) {
    Write-Step "Setting up virtual environment..."
    if ((Test-Path $venvPath) -and (-not $Force)) {
        Write-Success "Virtual environment exists"
    } else {
        if (Test-Path $venvPath) {
            Write-Step "Removing existing virtual environment..."
            Remove-Item $venvPath -Recurse -Force
        }
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create virtual environment"
            exit 1
        }
        Write-Success "Virtual environment created"
    }

    # Activate
    Write-Step "Activating virtual environment..."
    & "$venvPath\Scripts\Activate.ps1"
    Write-Success "Virtual environment activated"
}

# Upgrade pip
Write-Step "Upgrading pip..."
python -m pip install --upgrade pip -q
Write-Success "pip upgraded"

# Install dependencies
Write-Step "Installing dependencies..."
$requirements = "requirements.txt"
if (Test-Path $requirements) {
    $pipArgs = @("install", "-r", $requirements)
    if ($Dev) {
        $pipArgs += @("-r", "requirements-dev.txt")
    }
    python -m pip @pipArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install dependencies"
        exit 1
    }
    Write-Success "Dependencies installed"
} else {
    Write-Error "requirements.txt not found"
    exit 1
}

# Install Playwright browsers
Write-Step "Installing Playwright browsers..."
python -m playwright install chromium 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Success "Playwright browsers installed"
} else {
    Write-Warning "Playwright browser install failed (may need manual install)"
}

# Create .env from .env.example
Write-Step "Setting up configuration..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success "Created .env from .env.example"
        Write-Warning "Please edit .env with your API keys and settings"
    } else {
        Write-Error ".env.example not found"
    }
} else {
    Write-Success ".env already exists"
}

# Create required directories
Write-Step "Creating directories..."
$dirs = @("logs", "data", "projects", "temp", "jarvis\database\migrations")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Success "Directories created"

# Run diagnostics
Write-Step "Running diagnostics..."
$diagResult = python run.py --diagnose 2>&1
Write-Host $diagResult

# Summary
Write-Header "SETUP COMPLETE"

Write-Host "Next steps:"
Write-Host "  1. Edit .env with your API keys (OpenAI, Anthropic, etc.)"
Write-Host "  2. Run JARVIS: python run.py"
Write-Host "  3. CLI mode: python run.py --cli"
Write-Host "  4. Diagnostics: python run.py --diagnose"
Write-Host ""
Write-Host "Default hotkey: Ctrl+Space (toggle panel)"
Write-Host ""
Write-Host "Happy coding with JARVIS!" -ForegroundColor Green