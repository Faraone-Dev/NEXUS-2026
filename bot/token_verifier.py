"""
NEXUS AI Trading Bot - Token Verification
==========================================
Verifica holdings on-chain per tier access
"""

from web3 import Web3
from loguru import logger
from config import config
from typing import Optional, Dict

# Minimal ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# Chain configurations
CHAINS = {
    "base": {
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453,
        "name": "Base"
    },
    "bsc": {
        "rpc": "https://bsc-dataseed1.binance.org",
        "chain_id": 56,
        "name": "BSC"
    },
    "arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "chain_id": 42161,
        "name": "Arbitrum"
    },
    "polygon": {
        "rpc": "https://polygon-rpc.com",
        "chain_id": 137,
        "name": "Polygon"
    },
    "avalanche": {
        "rpc": "https://api.avax.network/ext/bc/C/rpc",
        "chain_id": 43114,
        "name": "Avalanche"
    }
}

# Tier thresholds (in tokens, not wei)
TIERS = {
    "DIAMOND": 1_000_000,
    "GOLD": 200_000,
    "SILVER": 50_000,
    "BRONZE": 10_000,
    "FREE": 0
}

# Tier features
TIER_FEATURES = {
    "DIAMOND": {
        "pairs": "unlimited",
        "signals_delay": 0,
        "auto_trade": True,
        "api_access": True,
        "priority_support": True
    },
    "GOLD": {
        "pairs": "unlimited",
        "signals_delay": 0,
        "auto_trade": True,
        "api_access": False,
        "priority_support": False
    },
    "SILVER": {
        "pairs": 5,
        "signals_delay": 0,
        "auto_trade": False,  # Testnet only
        "api_access": False,
        "priority_support": False
    },
    "BRONZE": {
        "pairs": 1,
        "signals_delay": 0,
        "auto_trade": False,
        "api_access": False,
        "priority_support": False
    },
    "FREE": {
        "pairs": 0,
        "signals_delay": 900,  # 15 min delay
        "auto_trade": False,
        "api_access": False,
        "priority_support": False
    }
}


class TokenVerifier:
    """Verify $NEXUS holdings across chains"""
    
    def __init__(self, token_addresses: Dict[str, str]):
        """
        Args:
            token_addresses: Dict mapping chain name to token contract address
                e.g. {"base": "0x...", "bsc": "0x..."}
        """
        self.token_addresses = token_addresses
        self.web3_instances = {}
        
        # Initialize Web3 for each chain
        for chain, addr in token_addresses.items():
            if chain in CHAINS:
                self.web3_instances[chain] = Web3(Web3.HTTPProvider(CHAINS[chain]["rpc"]))
                logger.info(f"Connected to {chain}: {CHAINS[chain]['name']}")
    
    def get_balance(self, wallet: str, chain: str) -> float:
        """Get token balance for wallet on specific chain"""
        
        if chain not in self.web3_instances:
            logger.warning(f"Chain {chain} not configured")
            return 0.0
        
        try:
            w3 = self.web3_instances[chain]
            token_address = self.token_addresses[chain]
            
            # Checksum addresses
            wallet = Web3.to_checksum_address(wallet)
            token_address = Web3.to_checksum_address(token_address)
            
            # Get contract
            contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
            
            # Get balance and decimals
            balance_wei = contract.functions.balanceOf(wallet).call()
            decimals = contract.functions.decimals().call()
            
            # Convert to human readable
            balance = balance_wei / (10 ** decimals)
            
            logger.debug(f"Balance on {chain}: {balance:,.2f} NEXUS")
            return balance
            
        except Exception as e:
            logger.error(f"Error getting balance on {chain}: {e}")
            return 0.0
    
    def get_total_balance(self, wallet: str) -> float:
        """Get total balance across all chains"""
        
        total = 0.0
        
        for chain in self.token_addresses:
            balance = self.get_balance(wallet, chain)
            total += balance
        
        logger.info(f"Total balance for {wallet[:10]}...: {total:,.2f} NEXUS")
        return total
    
    def get_tier(self, wallet: str) -> str:
        """Get user tier based on holdings"""
        
        total_balance = self.get_total_balance(wallet)
        
        for tier, threshold in TIERS.items():
            if total_balance >= threshold:
                logger.info(f"Wallet {wallet[:10]}... is tier: {tier}")
                return tier
        
        return "FREE"
    
    def get_tier_features(self, wallet: str) -> dict:
        """Get features available for user's tier"""
        
        tier = self.get_tier(wallet)
        features = TIER_FEATURES.get(tier, TIER_FEATURES["FREE"])
        
        return {
            "tier": tier,
            "features": features
        }
    
    def can_access_feature(self, wallet: str, feature: str) -> bool:
        """Check if wallet can access specific feature"""
        
        tier_info = self.get_tier_features(wallet)
        features = tier_info["features"]
        
        return features.get(feature, False)
    
    def verify_signature(self, wallet: str, message: str, signature: str) -> bool:
        """Verify wallet ownership via signature"""
        
        try:
            w3 = list(self.web3_instances.values())[0]  # Any chain works
            
            # Recover address from signature
            recovered = w3.eth.account.recover_message(
                text=message,
                signature=signature
            )
            
            return recovered.lower() == wallet.lower()
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False


# Convenience function
def verify_access(wallet: str, token_addresses: Dict[str, str]) -> dict:
    """Quick verification of wallet access"""
    
    verifier = TokenVerifier(token_addresses)
    return verifier.get_tier_features(wallet)


# Test
if __name__ == "__main__":
    # Example usage (replace with real addresses after deploy)
    TOKEN_ADDRESSES = {
        "base": "0x0000000000000000000000000000000000000000",  # Replace after deploy
        "bsc": "0x0000000000000000000000000000000000000000",
    }
    
    # Test wallet
    test_wallet = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # Vitalik
    
    verifier = TokenVerifier(TOKEN_ADDRESSES)
    
    # This will return 0 since token not deployed yet
    tier_info = verifier.get_tier_features(test_wallet)
    print(f"Tier: {tier_info['tier']}")
    print(f"Features: {tier_info['features']}")
