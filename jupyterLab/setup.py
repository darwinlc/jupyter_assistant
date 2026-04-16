from setuptools import setup, find_packages

setup(
    name="ai_jupyter_server",
    version="1.0.0",
    description="AI-powered completion, edit, and review for any file type in JupyterLab",
    packages=find_packages(),
    install_requires=[
        "jupyter_server>=2.0",
        "openai>=1.0",
        "tornado",
    ],
    entry_points={
        "jupyter_serverproxy_servers": [],
    },
    # Tells jupyter_server to auto-discover this extension
    data_files=[
        (
            "etc/jupyter/jupyter_server_config.d",
            ["jupyter_server_config.d/ai_jupyter_server.json"],
        )
    ],
)
