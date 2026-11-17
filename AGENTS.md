# finolabs/plugins

## Reviews

Pull requests follow `review-gate` "Pull requests"; reviewers may post their review comments on them. Pull requests may take the low-risk lane of `review-gate` (owner decision, 17/11/2026). The lane covers root-document edits such as the README and a catalog pin: a plugin catalog (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`) whose only changes are existing entries' `source.ref`, moved to a release tag `vX.Y.Z`, and their descriptions. Any other change stays outside the lane (enforcer: `merge_check.py --lane` from finolabs-vibecode 0.3.3 or later).
