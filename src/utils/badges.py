from pathlib import Path
from typing import Dict
from src.models.file_info import FileInfo
import logging

def generate_badges(file_manifest: Dict[str, FileInfo], repo_path: Path) -> str:
    """Generate appropriate badges based on repository content.
    
    Args:
        file_manifest: Dictionary of files in the repository
        repo_path: Path to the repository
        
    Returns:
        str: Space-separated string of markdown badges
    """
    badges = []
    
    # Check for license file to add license badge
    license_files = [f for f in file_manifest.keys() if 'license' in f.lower()]
    if license_files:
        try:
            license_file = license_files[0]
            license_content = Path(repo_path / license_file).read_text(encoding='utf-8', errors='ignore')
            
            # Detect license type
            if 'MIT' in license_content:
                badges.append("![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)")
            elif 'Apache' in license_content:
                badges.append("![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=for-the-badge)")
            elif 'GPL' in license_content:
                badges.append("![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg?style=for-the-badge)")
            elif 'BSD' in license_content:
                badges.append("![License: BSD](https://img.shields.io/badge/License-BSD-blue.svg?style=for-the-badge)")
            else:
                badges.append("![License](https://img.shields.io/badge/License-Custom-blue.svg?style=for-the-badge)")
        except Exception as e:
            logging.warning(f"Could not read license file: {e}")
            # If we can't read the license file, just add a generic license badge
            badges.append("![License](https://img.shields.io/badge/License-Custom-blue.svg?style=for-the-badge)")
    else:
        # Add a custom license badge even when no license file is found
        badges.append("![License](https://img.shields.io/badge/License-Custom-blue.svg?style=for-the-badge)")
    
    # Check for CI/CD configuration
    if any('.github/workflows' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)")
    elif any('azure-pipelines' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-Azure_Pipelines-2560E0?style=for-the-badge&logo=azure-pipelines&logoColor=white)")
    elif any('.travis.yml' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-Travis-B22222?style=for-the-badge&logo=travis&logoColor=white)")
    elif any('Jenkinsfile' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-Jenkins-D24939?style=for-the-badge&logo=jenkins&logoColor=white)")
    elif any('gitlab-ci.yml' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-GitLab-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white)")
    elif any('circleci' in f for f in file_manifest.keys()):
        badges.append("![CI/CD](https://img.shields.io/badge/CI%2FCD-CircleCI-343434?style=for-the-badge&logo=circleci&logoColor=white)")
    
    # Check for testing frameworks
    if any('junit' in f.lower() for f in file_manifest.keys()) or any('test' in f.lower() and '.java' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-JUnit-25A162?style=for-the-badge&logo=junit5&logoColor=white)")
    elif any('nunit' in f.lower() for f in file_manifest.keys()) or any('test' in f.lower() and '.cs' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-NUnit-008C45?style=for-the-badge&logo=dotnet&logoColor=white)")
    elif any('jest' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-Jest-C21325?style=for-the-badge&logo=jest&logoColor=white)")
    elif any('mocha' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-Mocha-8D6748?style=for-the-badge&logo=mocha&logoColor=white)")
    elif any('pytest' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)")
    elif any('rspec' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-RSpec-CC342D?style=for-the-badge&logo=ruby&logoColor=white)")
    elif any('cypress' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-Cypress-17202C?style=for-the-badge&logo=cypress&logoColor=white)")
    elif any('playwright' in f.lower() for f in file_manifest.keys()):
        badges.append("![Tests](https://img.shields.io/badge/Tests-Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)")
    
    # Check for documentation
    if any('docs/' in f for f in file_manifest.keys()):
        badges.append("![Documentation](https://img.shields.io/badge/Documentation-Yes-brightgreen?style=for-the-badge)")
    
    # Check for Docker
    if any('dockerfile' in f.lower() for f in file_manifest.keys()) or any('docker-compose' in f.lower() for f in file_manifest.keys()):
        badges.append("![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)")
    
    # Check for common languages/frameworks
    languages = set()
    
    # Java & Spring Boot
    if any('.java' in f.lower() for f in file_manifest.keys()):
        languages.add("![Java](https://img.shields.io/badge/Java-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)")
        
        # Check for Spring Boot
        if any('spring-boot' in f.lower() for f in file_manifest.keys()) or any('springboot' in f.lower() for f in file_manifest.keys()):
            languages.add("![Spring Boot](https://img.shields.io/badge/Spring_Boot-6DB33F?style=for-the-badge&logo=spring-boot&logoColor=white)")
        elif any('spring' in f.lower() for f in file_manifest.keys()):
            languages.add("![Spring](https://img.shields.io/badge/Spring-6DB33F?style=for-the-badge&logo=spring&logoColor=white)")
    
    # C# & ASP.NET
    if any('.cs' in f.lower() for f in file_manifest.keys()):
        languages.add("![C#](https://img.shields.io/badge/C%23-239120?style=for-the-badge&logo=c-sharp&logoColor=white)")
        
        # Check for ASP.NET
        if any('asp.net' in f.lower() for f in file_manifest.keys()) or any('aspnet' in f.lower() for f in file_manifest.keys()):
            languages.add("![ASP.NET](https://img.shields.io/badge/ASP.NET-5C2D91?style=for-the-badge&logo=.net&logoColor=white)")
        elif any('.net' in f.lower() for f in file_manifest.keys()):
            languages.add("![.NET](https://img.shields.io/badge/.NET-5C2D91?style=for-the-badge&logo=.net&logoColor=white)")
    
    # JavaScript/TypeScript & React
    if any('.js' in f.lower() for f in file_manifest.keys()):
        languages.add("![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)")
    
    if any('.ts' in f.lower() for f in file_manifest.keys()):
        languages.add("![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)")
    
    # React
    if any('react' in f.lower() for f in file_manifest.keys()):
        languages.add("![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)")
        
        # Check for React frameworks
        if any('next.js' in f.lower() for f in file_manifest.keys()) or any('nextjs' in f.lower() for f in file_manifest.keys()):
            languages.add("![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=next.js&logoColor=white)")
        if any('gatsby' in f.lower() for f in file_manifest.keys()):
            languages.add("![Gatsby](https://img.shields.io/badge/Gatsby-663399?style=for-the-badge&logo=gatsby&logoColor=white)")
    
    # Other popular frameworks
    if any('angular' in f.lower() for f in file_manifest.keys()):
        languages.add("![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)")
    
    if any('vue' in f.lower() for f in file_manifest.keys()):
        languages.add("![Vue.js](https://img.shields.io/badge/Vue.js-4FC08D?style=for-the-badge&logo=vue.js&logoColor=white)")
    
    # Python
    if any('.py' in f.lower() for f in file_manifest.keys()):
        languages.add("![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)")
        
        # Check for Python frameworks
        if any('django' in f.lower() for f in file_manifest.keys()):
            languages.add("![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)")
        if any('flask' in f.lower() for f in file_manifest.keys()):
            languages.add("![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)")
        if any('fastapi' in f.lower() for f in file_manifest.keys()):
            languages.add("![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)")
    
    # Ruby
    if any('.rb' in f.lower() for f in file_manifest.keys()):
        languages.add("![Ruby](https://img.shields.io/badge/Ruby-CC342D?style=for-the-badge&logo=ruby&logoColor=white)")
        if any('rails' in f.lower() for f in file_manifest.keys()):
            languages.add("![Rails](https://img.shields.io/badge/Rails-CC0000?style=for-the-badge&logo=ruby-on-rails&logoColor=white)")
    
    # PHP
    if any('.php' in f.lower() for f in file_manifest.keys()):
        languages.add("![PHP](https://img.shields.io/badge/PHP-777BB4?style=for-the-badge&logo=php&logoColor=white)")
        if any('laravel' in f.lower() for f in file_manifest.keys()):
            languages.add("![Laravel](https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white)")
    
    # Go
    if any('.go' in f.lower() for f in file_manifest.keys()):
        languages.add("![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)")
    
    # Rust
    if any('.rs' in f.lower() for f in file_manifest.keys()):
        languages.add("![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)")
    
    # Databases
    if any('mongodb' in f.lower() for f in file_manifest.keys()):
        languages.add("![MongoDB](https://img.shields.io/badge/MongoDB-4EA94B?style=for-the-badge&logo=mongodb&logoColor=white)")
    
    if any('mysql' in f.lower() for f in file_manifest.keys()):
        languages.add("![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white)")
    
    if any('postgresql' in f.lower() or 'postgres' in f.lower() for f in file_manifest.keys()):
        languages.add("![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)")
    
    if any('redis' in f.lower() for f in file_manifest.keys()):
        languages.add("![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)")
    
    # Add all detected languages to badges
    badges.extend(languages)
    
    # Return space-separated badges
    return " ".join(badges) 