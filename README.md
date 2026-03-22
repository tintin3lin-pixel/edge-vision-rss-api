# Edge Vision RSS Aggregator API

A lightweight Vercel serverless function that aggregates 30 tech signal sources and returns clean JSON for Dify workflows.

## Endpoints

- `GET /` or `GET /api/fetch` — Returns aggregated RSS data as JSON

## Response Format

```json
{
  "items": [
    {
      "title": "Article title",
      "link": "https://...",
      "pub_date": "...",
      "source": "Hacker News",
      "dimension": "developer"
    }
  ],
  "total": 87,
  "fetch_time": "2026-03-22 08:00 CST",
  "sources_summary": "Hacker News(15), TechCrunch(12), ...",
  "dim_summary": "developer:30, industry:25, ...",
  "failed_sources": []
}
```

## Sources Covered (30 total)

- Global Tech Media: Hacker News, TechCrunch, The Verge, Wired, MIT Tech Review, VentureBeat
- AI Labs: OpenAI Blog, Anthropic Blog, DeepMind Blog
- Developer/Research: HuggingFace, arXiv AI/ML, Papers with Code, BAIR Blog
- Reddit: r/MachineLearning, r/LocalLLaMA, r/artificial
- Capital/VC: a16z Blog, Sequoia Blog
- China Tech: 36Kr, Jiqizhixin, PingWest
- Analysis: Stratechery, Benedict Evans, Simon Willison, Lilian Weng
- Hardware: NVIDIA Blog
- Other: Product Hunt, Lex Fridman

## Deploy to Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new)

1. Fork or clone this repo
2. Connect to Vercel
3. Deploy — no environment variables needed
