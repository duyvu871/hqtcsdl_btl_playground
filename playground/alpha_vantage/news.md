# Alpha Vantage response

- **command:** `news`

## Request

```text
https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=IBM&time_from=20260421T1330&time_to=20260428T1330&limit=20&sort=RELEVANCE&apikey=%2A%2A%2A
```

## Response

```json
{
  "items": "50",
  "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
  "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
  "feed": [
    {
      "title": "HSBC Upgrades International Business Machines to Hold From Reduce, Adjusts PT to $231 From $218",
      "url": "https://www.moomoo.com/news/post/69008218/hsbc-upgrades-international-business-machines-to-hold-from-reduce-adjusts",
      "time_published": "20260428T100054",
      "authors": [],
      "summary": "HSBC has upgraded its rating for International Business Machines (IBM) from Reduce to Hold. The firm also adjusted its price target for IBM shares, increasing it from $218 to $231. This change reflects a more neutral outlook on the semiconductor giant's stock.",
      "banner_image": null,
      "source": "Moomoo",
      "category_within_source": "General",
      "source_domain": "Moomoo",
      "topics": [
        {
          "topic": "financial_markets",
          "relevance_score": "0.902438"
        },
        {
          "topic": "technology",
          "relevance_score": "0.709160"
        },
        {
          "topic": "finance",
          "relevance_score": "0.614865"
        }
      ],
      "overall_sentiment_score": 0.441684,
      "overall_sentiment_label": "Bullish",
      "ticker_sentiment": [
        {
          "ticker": "IBM",
          "relevance_score": "1.000000",
          "ticker_sentiment_score": "0.409842",
          "ticker_sentiment_label": "Bullish"
        }
      ]
    },
    {
      "title": "Cisco’s Universal Quantum Switch and the rise of the quantum fabric",
      "url": "https://siliconangle.com/2026/04/27/ciscos-universal-quantum-switch-rise-quantum-fabric/",
      "time_published": "20260428T030718",
      "authors": [
        "Zeus Kerravala"
      ],
      "summary": "Cisco's new Universal Quantum Switch signifies a critical shift in quantum computing from isolated hardware to an interconnected fabric, allowing distributed quantum processors to function as a single logical machine. This switch, which routes entangled photons at room temperature over standard telecom fiber, addresses the scaling challenge of quantum systems and positions Cisco as a key enabler of heterogeneous quantum data centers and quantum-enhanced classical applications. IT leaders are advised to prepare for this future by treating quantum as a multivendor, networked service and building quantum-literate teams.",
      "banner_image": "https://s3.us-west-2.amazonaws.com/cube365-prod/related-content/e810e50d-1091-4ce3-9cc2-0232848a8d60.png",
      "source": "SiliconANGLE",
      "category_within_source": "General",
      "source_domain": "SiliconANGLE",
      "topics": [
        {
          "topic": "technology",
          "relevance_score": "1.000000"
        }
      ],
      "overall_sentiment_score": 0.291558,
      "overall_sentiment_label": "Somewhat-Bullish",
      "ticker_sentiment": [
        {
          "ticker": "CSCO",
          "relevance_score": "1.000000",
          "ticker_sentiment_score": "0.436031",
          "ticker_sentiment_label": "Bullish"
        },
        {
          "ticker": "IBM",
          "relevance_score": "0.635282",
          "ticker_sentiment_score": "0.250045",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "MSFT",
          "relevance_score": "0.581271",
          "ticker_sentiment_score": "0.110538",
          "ticker_sentiment_label": "Neutral"
        }
      ]
    },
    {
      "title": "IBM Quantum And AI Security Push Puts Long Term Thesis In Focus",
      "url": "https://simplywall.st/stocks/us/software/nyse-ibm/international-business-machines/news/ibm-quantum-and-ai-security-push-puts-long-term-thesis-in-fo",
      "time_published": "20260428T003743",
      "authors": [
        "Simply Wall St",
        "Bailey Pemberton"
      ],
      "summary": "IBM is expanding its quantum computing footprint through a partnership with the University of Illinois and rolling out autonomous, AI-driven security solutions. These initiatives aim to integrate quantum computing and AI into real-world infrastructure and security, repositioning IBM's technology stack beyond traditional software. The moves highlight IBM's strategy to align research, products, and consulting to generate revenue from high-profile technology advancements.",
      "banner_image": null,
      "source": "Simply Wall Street",
      "category_within_source": "General",
      "source_domain": "Simply Wall Street",
      "topics": [
        {
          "topic": "technology",
          "relevance_score": "0.906971"
        },
        {
          "topic": "earnings",
          "relevance_score": "0.843219"
        }
      ],
      "overall_sentiment_score": -0.029476,
      "overall_sentiment_label": "Neutral",
      "ticker_sentiment": [
        {
          "ticker": "IBM",
          "relevance_score": "1.000000",
          "ticker_sentiment_score": "0.349974",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "MSFT",
          "relevance_score": "0.639388",
          "ticker_sentiment_score": "-0.141043",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "AMZN",
          "relevance_score": "0.600406",
          "ticker_sentiment_score": "-0.137746",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "GOOGL",
          "relevance_score": "0.628208",
          "ticker_sentiment_score": "-0.126648",
          "ticker_sentiment_label": "Neutral"
        }
      ]
    },
    {
      "title": "Nvidia stock hits new all-time high amid market cap speculation",
      "url": "https://cryptobriefing.com/nvidia-stock-hits-new-all-time-high-amid-market-cap-speculation/",
      "time_published": "20260427T165205",
      "authors": [
        "Estefano Gomez"
      ],
      "summary": "Nvidia's stock has reached a new all-time high, increasing the likelihood on Polymarket that it will be the largest company by market cap on June 30, with odds at 92.5%. This surge, however, does not significantly impact its chances of being the second-largest company by April 30, which remain extremely low. Traders are advised to monitor Nvidia's Q2 earnings and AI contract announcements as potential market movers.",
      "banner_image": "https://static.cryptobriefing.com/wp-content/uploads/2026/04/27125048/largest-company-eoy-KS99l6lbxfCc-88-457x457.jpg",
      "source": "Crypto Briefing",
      "category_within_source": "General",
      "source_domain": "Crypto Briefing",
      "topics": [
        {
          "topic": "financial_markets",
          "relevance_score": "0.924191"
        },
        {
          "topic": "technology",
          "relevance_score": "0.896576"
        },
        {
          "topic": "earnings",
          "relevance_score": "0.647576"
        }
      ],
      "overall_sentiment_score": 0.182606,
      "overall_sentiment_label": "Somewhat-Bullish",
      "ticker_sentiment": [
        {
          "ticker": "NVDA",
          "relevance_score": "1.000000",
          "ticker_sentiment_score": "0.470647",
          "ticker_sentiment_label": "Bullish"
        },
        {
          "ticker": "AAPL",
          "relevance_score": "0.630070",
          "ticker_sentiment_score": "-0.125625",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "INTC",
          "relevance_score": "0.721182",
          "ticker_sentiment_score": "0.328176",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "IBM",
          "relevance_score": "0.644089",
          "ticker_sentiment_score": "0.126246",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "MSFT",
          "releva
... (96098 ký tự còn lại)
```
