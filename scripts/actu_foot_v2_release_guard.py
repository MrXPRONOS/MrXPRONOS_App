"""Read-only verification of actual GitHub environment rules, fail closed on writes."""
import os
import requests
from scripts.actu_foot_github_vault import VaultError

ENVIRONMENT="actu-foot-v2-maintenance"

def validate(environment, policies):
    rules=environment.get("protection_rules") or []
    review=next((r for r in rules if r.get("type")=="required_reviewers"),None)
    if not review or not review.get("reviewers"):
        raise VaultError("V2_ENV_REQUIRED_REVIEWERS_MISSING")
    branch=environment.get("deployment_branch_policy") or {}
    if branch.get("custom_branch_policies") is not True or branch.get("protected_branches") is not False:
        raise VaultError("V2_ENV_EXPLICIT_MAIN_POLICY_REQUIRED")
    if {(p.get("name"),p.get("type","branch")) for p in policies}!={("main","branch")}:
        raise VaultError("V2_ENV_ONLY_MAIN_REQUIRED")
    if environment.get("can_admins_bypass") is not False:
        raise VaultError("V2_ENV_ADMIN_BYPASS_MUST_BE_DISABLED")
    return True

def main():
    repo=os.environ["GITHUB_REPOSITORY"]
    token=os.environ["GITHUB_TOKEN"]
    url=f"https://api.github.com/repos/{repo}/environments/{ENVIRONMENT}"
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28"}
    def get(path):
        response=requests.get(url+path,headers=headers,timeout=20)
        if response.status_code!=200:
            raise VaultError("V2_ENV_READ_DENIED_"+str(response.status_code))
        return response.json()
    environment=get("")
    policy=get("/deployment-branch-policies?per_page=100")
    if policy.get("total_count")!=1 or not isinstance(policy.get("branch_policies"),list):
        raise VaultError("V2_ENV_ONLY_MAIN_REQUIRED")
    validate(environment,policy["branch_policies"])
    print("V2_ENV_PROTECTION_VERIFIED")

if __name__=="__main__":
    main()
