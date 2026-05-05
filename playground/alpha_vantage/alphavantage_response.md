# Alpha Vantage response

- **command:** `news`

## Request

```text
https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=CRYPTO%3ABTC%2CCRYPTO%3AETH&time_from=20260421T1409&time_to=20260428T1409&limit=20&sort=RELEVANCE&apikey=%2A%2A%2A
```

## Response

```json
{
  "items": "50",
  "sentiment_score_definition": "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
  "relevance_score_definition": "0 < x <= 1, with a higher score indicating higher relevance.",
  "feed": [
    {
      "title": "Ethereum Risks 10% Dip Versus Bitcoin Despite ETH Staking Milestone",
      "url": "https://cointelegraph.com/markets/ethereum-decline-10percent-versus-bitcoin-despite-record-eth-staking",
      "time_published": "20260422T161907",
      "authors": [],
      "summary": "Ethereum's record 32.33% staking ratio is shrinking liquid supply, reducing sell pressure and potentially supporting an ETH price recovery over time.",
      "banner_image": "https://s3.cointelegraph.com/uploads/2026-04/019db5b1-5913-7637-a380-f8460a161cee.png",
      "source": "Cointelegraph",
      "category_within_source": "n/a",
      "source_domain": "cointelegraph.com",
      "topics": [
        {
          "topic": "Financial Markets",
          "relevance_score": "0.108179"
        }
      ],
      "overall_sentiment_score": -0.15808,
      "overall_sentiment_label": "Somewhat-Bearish",
      "ticker_sentiment": [
        {
          "ticker": "BMNR",
          "relevance_score": "0.095517",
          "ticker_sentiment_score": "0.0",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "CRYPTO:BTC",
          "relevance_score": "0.850133",
          "ticker_sentiment_score": "-0.40824",
          "ticker_sentiment_label": "Bearish"
        },
        {
          "ticker": "CRYPTO:ETH",
          "relevance_score": "0.928139",
          "ticker_sentiment_score": "-0.247459",
          "ticker_sentiment_label": "Somewhat-Bearish"
        }
      ]
    },
    {
      "title": "Ethereum To $250,000? Daredevil Thesis Says ETH Could Replace Bitcoin, Gold As Money",
      "url": "https://www.benzinga.com/crypto/cryptocurrency/26/04/51972316/ethereum-to-250000-daredevil-thesis-says-eth-could-replace-bitcoin-gold-as-money",
      "time_published": "20260422T145247",
      "authors": [
        "Parshwa Turakhiya"
      ],
      "summary": "Gold's monetary premium sits at approximately $29.7 trillion. Bitcoin's monetary premium is around $1.5 trillion. Together, they represent roughly $31.1 trillion held by people who want money outside government control. ETH's current market cap is approximately $280 billion-less than 1% of that ...",
      "banner_image": "https://cdn.benzinga.com/files/images/story/2026/04/22/Bitcoin-and-Ethereum.jpeg?width=1200&height=800&fit=crop",
      "source": "Benzinga",
      "category_within_source": "Markets",
      "source_domain": "www.benzinga.com",
      "topics": [
        {
          "topic": "Economy - Monetary",
          "relevance_score": "0.310843"
        },
        {
          "topic": "Financial Markets",
          "relevance_score": "0.161647"
        },
        {
          "topic": "Technology",
          "relevance_score": "0.5"
        },
        {
          "topic": "Finance",
          "relevance_score": "0.5"
        },
        {
          "topic": "Blockchain",
          "relevance_score": "0.158519"
        }
      ],
      "overall_sentiment_score": 0.016594,
      "overall_sentiment_label": "Neutral",
      "ticker_sentiment": [
        {
          "ticker": "GOOG",
          "relevance_score": "0.098659",
          "ticker_sentiment_score": "0.163517",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "SCHW",
          "relevance_score": "0.098659",
          "ticker_sentiment_score": "0.091004",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "BRK-A",
          "relevance_score": "0.098659",
          "ticker_sentiment_score": "-0.006472",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "CRYPTO:BTC",
          "relevance_score": "0.543004",
          "ticker_sentiment_score": "0.085948",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "CRYPTO:ETH",
          "relevance_score": "0.952685",
          "ticker_sentiment_score": "0.017073",
          "ticker_sentiment_label": "Neutral"
        }
      ]
    },
    {
      "title": "ETH Triple Top Rejects $2.4K As Analysts Flag Weakness Against BTC",
      "url": "https://cointelegraph.com/markets/ether-triple-top-pattern-rejects-24k-as-eth-analyst-questions-uptrend",
      "time_published": "20260427T231940",
      "authors": [],
      "summary": "Ether charts flash an ominous triple-top pattern as ETH fails to overcome $2,400. Will bears maintain control over the altcoin's price action?",
      "banner_image": "https://resizer.cointelegraph.com/cdn-cgi/image/f=auto,onerror=redirect,w=896,q=90/https://payload.cointelegraph.com/api/media/file/019dd051-72c1-77d7-96c1-77950736252b.png?prefix=media%2Fcontent",
      "source": "Cointelegraph",
      "category_within_source": "n/a",
      "source_domain": "cointelegraph.com",
      "topics": [
        {
          "topic": "Blockchain",
          "relevance_score": "0.158519"
        }
      ],
      "overall_sentiment_score": -0.141832,
      "overall_sentiment_label": "Neutral",
      "ticker_sentiment": [
        {
          "ticker": "CRYPTO:BTC",
          "relevance_score": "0.479683",
          "ticker_sentiment_score": "-0.022156",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "CRYPTO:ETH",
          "relevance_score": "0.801457",
          "ticker_sentiment_score": "-0.158313",
          "ticker_sentiment_label": "Somewhat-Bearish"
        }
      ]
    },
    {
      "title": "Crypto Market Maker GSR Launches Multi-Asset Crypto ETF",
      "url": "https://cointelegraph.com/news/crypto-market-maker-gsr-launched-multi-asset-etf",
      "time_published": "20260423T044654",
      "authors": [],
      "summary": "The GSR Crypto Core3 ETF is GSR's first crypto exchange-traded product, giving investors access to the top three largest cryptocurrencies by market capitalization.",
      "banner_image": "https://s3.cointelegraph.com/uploads/2026-04/019db89e-7406-7b00-ba46-6e952e6b8c49.png",
      "source": "Cointelegraph",
      "category_within_source": "n/a",
      "source_domain": "cointelegraph.com",
      "topics": [
        {
          "topic": "Finance",
          "relevance_score": "1.0"
        },
        {
          "topic": "Blockchain",
          "relevance_score": "0.576289"
        },
        {
          "topic": "Financial Markets",
          "relevance_score": "0.998663"
        }
      ],
      "overall_sentiment_score": 0.238736,
      "overall_sentiment_label": "Somewhat-Bullish",
      "ticker_sentiment": [
        {
          "ticker": "SCHW",
          "relevance_score": "0.107495",
          "ticker_sentiment_score": "0.0",
          "ticker_sentiment_label": "Neutral"
        },
        {
          "ticker": "AWON",
          "relevance_score": "0.107495",
          "ticker_sentiment_score": "0.205144",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "GS",
          "relevance_score": "0.213048",
          "ticker_sentiment_score": "0.253657",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "MS",
          "relevance_score": "0.107495",
          "ticker_sentiment_score": "0.177675",
          "ticker_sentiment_label": "Somewhat-Bullish"
        },
        {
          "ticker": "CRYPTO:BTC",
          "relevance_score": "0.776097",
          "ticker_sentiment_score": "0.422899",
          "ticker_sentiment_label": "Bullish"
        },
        {
          "ticker": "CRYPTO:ETH",
          "relevance_score": "0.500753",
          "ticker_sentiment_score": "0.193027",
          "ticker_sentiment_label": "Somewhat-Bullish"
        }
      ]
    },
    {
      "title": "Tom Le
... (87964 ký tự còn lại)
```
