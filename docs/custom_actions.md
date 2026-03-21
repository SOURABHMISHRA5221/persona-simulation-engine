# Custom Action Sets

Instead of standard LIKE or DISLIKE options, you can define any set of actions your specific product domain needs to measure. 

The simulation dynamically adapts its prompts, aggregation logic, and formatting entirely based on the JSON action set you specify.

## Defining Your Own Action Set

Create a file at `data/actions/my_domain.json`:

```json
{
  "action_set_id": "my_domain",
  "description": "What this action set measures",
  "primary_action_label": "ACTION",
  "actions": [
    { 
      "id": "ADOPT",   
      "label": "Adopt",   
      "emoji": "🚀", 
      "sentiment": "positive", 
      "description": "User would adopt this immediately." 
    },
    { 
      "id": "WAIT",    
      "label": "Wait",    
      "emoji": "⏳", 
      "sentiment": "neutral",  
      "description": "User would wait and see before acting." 
    },
    { 
      "id": "REJECT",  
      "label": "Reject",  
      "emoji": "❌", 
      "sentiment": "negative", 
      "description": "User would actively refuse or complain about this." 
    }
  ],
  "approval_actions": ["ADOPT"],
  "verdict_thresholds": {
    "strong_approval": 65,
    "mixed": 45,
    "majority_opposition": 25
  }
}
```

## Running Simulations with Custom Actions

Pass your newly created file to the CLI via the `--actions` flag.

```bash
python3 main.py --campaign "Migrate to new API v2" --actions data/actions/my_domain.json
```

### Pre-built Examples Available
- E-commerce: `--actions data/actions/ecommerce.json` (PURCHASE / WISHLIST / IGNORE / REPORT)
- Social media: `--actions data/actions/social.json` (SHARE / COMMENT / SCROLL_PAST / HIDE)
