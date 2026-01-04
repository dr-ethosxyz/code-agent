from github import GithubIntegration
import os
from dotenv import load_dotenv

load_dotenv()

app_id = os.getenv("GITHUB_APP_ID")
private_key = os.getenv("GITHUB_PRIVATE_KEY")
print(f"App ID: {app_id}")
print(f"Key starts with: {private_key[:30] if private_key else 'None'}")

private_key = private_key.replace("\\n", "\n")

integration = GithubIntegration(integration_id=int(app_id), private_key=private_key)
installations = list(integration.get_installations())

for inst in installations:
    print(f"Installation ID: {inst.id}, Account: {inst.account.login}")
