# Data Store Directory

This folder contains runtime data for NEXUS AI.

## Files

- `nexus.db` - SQLite database with trade history, scans, whale alerts
- `positions.json` - Current open positions
- `learning_insights.json` - Latest learning analysis results

## Database Schema

### trades
- All executed trades with entry/exit prices, PnL, AI scores

### scans  
- All token scans (including skipped ones) for learning

### whale_alerts
- Large transaction alerts for tracked tokens

## Backup

Recommended: backup `nexus.db` regularly for data preservation.
