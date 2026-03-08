"""
GitHub repository processor module.
Extracts content from GitHub repositories using the GitHub API.
"""

import re
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests
from urllib.parse import urlparse


class GitHubProcessor:
    """Process GitHub repositories and extract relevant content."""
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the GitHub processor.
        
        Args:
            github_token: GitHub API token (optional, increases rate limits)
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.api_base = "https://api.github.com"
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"
        
        self.timeout = 10
        self.max_readme_length = 10000
    
    def process(self, repo_url: str, user_id: str) -> Dict[str, Any]:
        """
        Process a GitHub repository URL and extract content.
        
        Args:
            repo_url: GitHub repository URL
            user_id: The user ID for tracking
        
        Returns:
            Dict with:
            - content: Extracted content as text
            - metadata: Repository metadata
            - languages: Programming languages used
            - validation: Validation results
        """
        
        # Validate and parse URL
        validation = self._validate_repo_url(repo_url)
        if not validation["is_valid"]:
            return {
                "content": "",
                "metadata": {"error": validation["error"]},
                "languages": [],
                "validation": validation,
            }
        
        owner, repo_name = validation["owner"], validation["repo"]
        
        try:
            # Fetch repository metadata
            repo_info = self._fetch_repo_info(owner, repo_name)
            if not repo_info:
                return {
                    "content": "",
                    "metadata": {
                        "error": "Failed to fetch repository info. The GitHub API may be rate-limited or the repo may not exist.",
                        "source_type": "github_repo",
                        "repo_url": repo_url,
                        "repo_name": repo_name,
                        "owner": owner,
                        "user_id": user_id,
                    },
                    "languages": [],
                    "validation": validation,
                }
            
            # Fetch README
            readme_content = self._fetch_readme(owner, repo_name)
            
            # Fetch languages
            languages = self._fetch_languages(owner, repo_name)
            
            # Fetch file tree for extra signal
            default_branch = repo_info.get("default_branch", "main")
            file_paths = self._fetch_tree(owner, repo_name, default_branch)
            
            # Construct content
            content = self._construct_content(repo_info, readme_content, languages, file_paths)
            
            # Build metadata
            metadata = {
                "source_type": "github_repo",
                "repo_url": repo_url,
                "repo_name": repo_name,
                "owner": owner,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "repo_id": repo_info.get("id"),
                "description": repo_info.get("description", ""),
                "stars": repo_info.get("stargazers_count", 0),
                "forks": repo_info.get("forks_count", 0),
                "open_issues": repo_info.get("open_issues_count", 0),
                "created_at": repo_info.get("created_at"),
                "updated_at": repo_info.get("updated_at"),
                "topics": repo_info.get("topics", []),
                "languages": languages,
                "is_fork": repo_info.get("fork", False),
                "license": (repo_info.get("license") or {}).get("name"),
            }
            
            return {
                "content": content,
                "metadata": metadata,
                "languages": languages,
                "validation": validation,
            }
        
        except Exception as e:
            return {
                "content": "",
                "metadata": {"error": f"Processing error: {str(e)}"},
                "languages": [],
                "validation": validation,
            }
    
    def _validate_repo_url(self, url: str) -> Dict[str, Any]:
        """Validate GitHub repository URL."""
        # Remove trailing slash and .git suffix
        url = url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        
        # Pattern for GitHub URLs
        pattern = r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)$"
        match = re.match(pattern, url)
        
        if not match:
            return {
                "is_valid": False,
                "error": "Invalid GitHub repository URL",
                "url": url,
            }
        
        owner, repo = match.groups()
        
        # Validate owner and repo name format
        if not re.match(r"^[\w\-\.]+$", owner) or not re.match(r"^[\w\-\.]+$", repo):
            return {
                "is_valid": False,
                "error": "Invalid owner or repository name format",
                "owner": owner,
                "repo": repo,
            }
        
        return {
            "is_valid": True,
            "url": url,
            "owner": owner,
            "repo": repo,
        }
    
    def _fetch_repo_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch repository information from GitHub API."""
        url = f"{self.api_base}/repos/{owner}/{repo}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching repo info: {e}")
            return None
    
    def _fetch_readme(self, owner: str, repo: str) -> str:
        """Fetch README content from GitHub API."""
        url = f"{self.api_base}/repos/{owner}/{repo}/readme"
        
        try:
            response = requests.get(
                url,
                headers={**self.headers, "Accept": "application/vnd.github.v3.raw"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.text
            # Limit length
            return content[:self.max_readme_length]
        except requests.RequestException:
            return ""
    
    def _fetch_languages(self, owner: str, repo: str) -> List[str]:
        """Fetch programming languages used in the repository."""
        url = f"{self.api_base}/repos/{owner}/{repo}/languages"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            languages = response.json()
            # Return languages sorted by frequency (descending)
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            return [lang[0] for lang in sorted_langs][:10]  # Top 10 languages
        except requests.RequestException:
            return []
    
    def _fetch_tree(self, owner: str, repo: str, branch: str = "main") -> List[str]:
        """Fetch the file tree (paths) from the repo's default branch."""
        url = f"{self.api_base}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 404 and branch == "main":
                # Try 'master' as fallback
                url = f"{self.api_base}/repos/{owner}/{repo}/git/trees/master?recursive=1"
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            tree = response.json().get("tree", [])
            return [item["path"] for item in tree if item.get("type") == "blob"][:200]
        except requests.RequestException:
            return []

    def _construct_content(
        self,
        repo_info: Dict[str, Any],
        readme: str,
        languages: List[str],
        file_paths: Optional[List[str]] = None,
    ) -> str:
        """Construct a text representation of the repository."""
        parts = []
        
        # Repository name and description
        if repo_info.get("full_name"):
            parts.append(f"Repository: {repo_info['full_name']}")
        
        if repo_info.get("description"):
            parts.append(f"Description: {repo_info['description']}")
        
        # Languages
        if languages:
            parts.append(f"Languages: {', '.join(languages)}")
        
        # Repository stats
        parts.append(f"Stars: {repo_info.get('stargazers_count', 0)}")
        parts.append(f"Forks: {repo_info.get('forks_count', 0)}")
        
        # Topics
        if repo_info.get("topics"):
            parts.append(f"Topics: {', '.join(repo_info['topics'])}")
        
        # File tree — helps Gemini infer tech stack from filenames
        if file_paths:
            # Highlight notable config / tech-signal files
            signal_files = [
                f for f in file_paths
                if any(kw in f.lower() for kw in [
                    "dockerfile", "docker-compose", ".github/workflows",
                    "package.json", "requirements.txt", "pyproject.toml",
                    "tsconfig", "tailwind", "next.config", "vite.config",
                    "jest.config", "pytest", ".eslint", "webpack",
                    "setup.py", "setup.cfg", "makefile", "cmake",
                    "terraform", "k8s", "kubernetes", "helm",
                    ".env", "api/", "routes", "schema", "model",
                    "test", "spec", "__test__",
                ])
            ]
            if signal_files:
                parts.append(f"\nNotable files: {', '.join(signal_files[:40])}")

            # Show directory structure overview (top-level + first-level dirs)
            top_dirs = sorted(set(
                f.split('/')[0] for f in file_paths if '/' in f
            ))
            if top_dirs:
                parts.append(f"Project directories: {', '.join(top_dirs[:30])}")

            parts.append(f"Total files: {len(file_paths)}")

        # README
        if readme:
            parts.append("\n--- README ---\n")
            parts.append(readme)
        
        return "\n".join(parts)


# Example usage
if __name__ == "__main__":
    processor = GitHubProcessor()
    
    # Test with a real repository
    test_url = "https://github.com/openai/gpt-3"
    result = processor.process(test_url, user_id="user_123")
    
    print(f"Content length: {len(result['content'])}")
    print(f"Languages: {result['languages']}")
    print(f"Metadata: {result['metadata']}")
