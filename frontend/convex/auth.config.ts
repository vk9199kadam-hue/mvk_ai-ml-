export default {
  providers: [
    {
      domain: "https://accounts.google.com",
      applicationID: "", // Set GOOGLE_CLIENT_ID in Convex env vars
    },
    {
      domain: "https://github.com/login/oauth",
      applicationID: "", // Set GITHUB_CLIENT_ID in Convex env vars
    },
    // V5 Enterprise SSO / SAML Placeholders
    {
      domain: "https://your-tenant.us.auth0.com", // Enterprise Auth0 SAML Connection
      applicationID: "auth0_saml_client_id_placeholder",
    },
    {
      domain: "https://your-org.okta.com/oauth2/default", // Enterprise Okta SSO
      applicationID: "okta_sso_client_id_placeholder",
    },
  ],
};

