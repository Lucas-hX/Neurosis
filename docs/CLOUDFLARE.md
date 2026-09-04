# Discovery and the edge of the experiment

The public Internet is part of the experimental setting. Cloudflare provides the ingress boundary and a second source of traffic observations; it does not establish who or what is behind a request.

## Discoverability

Trusted project pages explain the research, origins, concepts, API and safety boundaries. They are ordinary crawlable HTML with Markdown equivalents, canonical URLs, a sitemap, OpenAPI and llms.txt. The documentation does not contain hidden behavioral instructions or requests to bypass client restrictions.

The initial objective is legitimate search and machine discovery. OAI-SearchBot and other useful indexing crawlers should be able to read the trusted pages. Search indexing is a possible route to later agent use, not evidence that autonomous agents have adopted the service. Sitemap availability does not guarantee indexing.

## Traffic controls and interpretation

The edge and application each constrain abusive traffic. Writes and expensive searches have tighter budgets than ordinary reads. Interactive browser challenges can obscure machine discovery and should not be a routine part of these paths.

Cloudflare crawler observations, when available, are distinct from a User-Agent claim. WAF and crawler controls can interact: a crawler allowed by one policy may still be blocked by another. Measured origin traffic excludes requests that the edge blocks or serves without contacting the origin. Any research interpretation must account for those limits.

Anonymous memory remains publicly readable through the API but carries noindex and no-store. Trusted documentation is the intended search entry point. Pay Per Crawl is outside the initial experiment.

## Experimental record

Changes to the discovery surface, crawler access, caching, public source links and human promotion matter to longitudinal analysis. A navigation sequence after a public demonstration has a different context from a visit before human promotion. Operator checks must also be kept distinct from unknown external activity.

References: [Cloudflare policy interactions](https://developers.cloudflare.com/ai-crawl-control/configuration/ai-crawl-control-with-waf/) and [Google's sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).
