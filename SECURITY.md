# Security and privacy

soloPAW does not require a cloud service. Profile switching and authoring are local operations.

Never commit credentials, GitHub tokens, SSH private keys, `.env` files, shell history, or copied home-directory configuration.

For a suspected privacy leak in a public artifact, remove the artifact from distribution first and rotate any exposed credential. Git history may retain removed secrets, so use GitHub's sensitive-data removal guidance when necessary.
