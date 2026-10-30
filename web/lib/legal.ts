/**
 * Legal documents. These are intentionally placeholders: the operator must supply policy text reviewed by
 * counsel for each jurisdiction before launch. Replace the `body` strings (or load them from your CMS).
 */
export type LegalDoc = { title: string; sections: { heading: string; body: string }[] };

const REQUIRED = "This section must be completed by the operator and reviewed by qualified legal counsel before launch.";

export const legalDocs: Record<string, LegalDoc> = {
  terms: {
    title: "Terms & Conditions",
    sections: [
      { heading: "Eligibility and age", body: `Players must meet the minimum legal age in their jurisdiction (at least 18). ${REQUIRED}` },
      { heading: "Jurisdiction restrictions", body: `List the territories where the service is not offered. ${REQUIRED}` },
      { heading: "Promotions and rewards", body: `General rules for promotions, claims and fulfilment. Individual terms are shown on each promotion. ${REQUIRED}` },
      { heading: "Accounts and security", body: `Account responsibilities, restrictions and termination. ${REQUIRED}` },
    ],
  },
  privacy: {
    title: "Privacy Policy",
    sections: [
      { heading: "Information we collect", body: "Account details (username, email), activity needed to run promotions, referrals and support, and security logs." },
      { heading: "How it is used and shared", body: `${REQUIRED}` },
      { heading: "Your rights and contact", body: `${REQUIRED}` },
    ],
  },
  "responsible-gaming": {
    title: "Responsible Gaming",
    sections: [
      { heading: "Play within your limits", body: "Only play with money you can afford to lose and take regular breaks. If gaming stops being fun, stop." },
      { heading: "Getting help", body: `Add the support organisations and self-exclusion tools that apply in your operating jurisdictions. ${REQUIRED}` },
    ],
  },
};
