# Personas

The simulation acts through the perspectives of entirely distinct AI personas. 

## Persona Schema

Each persona in `data/user_profiles.json` includes demographic data, personality traits on a [0-1] scale, activity patterns, and past historical context.

```json
{
  "user_id": "user_001",
  "username": "alex_budget",
  "persona": {
    "age": 24,
    "occupation": "Student",
    "location": "Austin, TX",
    "interests": ["gaming", "open-source", "tech news"],
    "values": ["affordability", "transparency", "community"],
    "traits": {
      "price_sensitivity": 0.95,
      "tech_savviness": 0.75,
      "brand_loyalty": 0.30,
      "optimism": 0.50,
      "skepticism": 0.70,
      "community_orientation": 0.80
    },
    "behavior": {
      "avg_session_minutes": 25,
      "engagement_rate": 0.65,
      "subscription_tier": "free",
      "account_age_months": 14
    },
    "past_opinions": ["Frustrated by last year's outage.", "Loves the new mobile app update."],
    "hourly_activity": [0.02, 0.01, 0.05, 0.15, ...]
  }
}
```

## LLM-Powered User Generation

We created an auxiliary script explicitly to generate diverse, realistic user personas to seed the simulation environment while ensuring they don't form homogeneous echo chambers.

```bash
# Generate 10 new personas (auto-avoids existing archetypes)
python3 generate_users.py --count 10

# Focus on specific demographics
python3 generate_users.py --count 5 --type "elderly retiree, rural farmer, crypto enthusiast"

# One persona at a time for maximum diversity (slower, zero repetition)
python3 generate_users.py --count 20 --batch-size 1
```
