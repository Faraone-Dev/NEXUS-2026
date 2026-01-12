// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
 * ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
 * ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
 * ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
 * ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║
 * ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝ ╚══════╝
 * 
 * NEXUS AI - The Future Runs on Intelligence
 * https://nexus-ai.xyz
 * 
 * AI-Powered Trading Bot Token
 * Hold $NEXUS = Access the Bot
 */

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract NexusToken is ERC20, ERC20Burnable, Ownable, ReentrancyGuard {
    
    // ============ SUPPLY ============
    uint256 public constant TOTAL_SUPPLY = 1_000_000_000 * 10**18; // 1 Billion
    
    // ============ TAXES ============
    uint256 public buyTax = 2;      // 2%
    uint256 public sellTax = 3;     // 3%
    uint256 public transferTax = 0; // 0%
    
    // ============ LIMITS ============
    uint256 public maxWallet;       // 2% = 20M tokens
    uint256 public maxTx;           // 1% = 10M tokens
    uint256 public sellCooldown = 1 hours;
    
    // ============ WALLETS ============
    address public liquidityWallet;
    address public stakingWallet;
    address public burnAddress = 0x000000000000000000000000000000000000dEaD;
    
    // ============ AMM ============
    mapping(address => bool) public isAMM;
    
    // ============ EXCLUSIONS ============
    mapping(address => bool) public isExcludedFromFees;
    mapping(address => bool) public isExcludedFromLimits;
    
    // ============ ANTI-BOT ============
    uint256 public launchBlock;
    uint256 public deadBlocks = 3;
    mapping(address => bool) public isBlacklisted;
    mapping(address => uint256) public lastSellTime;
    
    // ============ TRADING ============
    bool public tradingEnabled = false;
    bool public limitsEnabled = true;
    
    // ============ EVENTS ============
    event TradingEnabled(uint256 blockNumber);
    event LimitsRemoved();
    event BlacklistUpdated(address indexed account, bool isBlacklisted);
    event ExcludedFromFees(address indexed account, bool isExcluded);
    event TaxesUpdated(uint256 buyTax, uint256 sellTax);
    event AMMUpdated(address indexed pair, bool isAMM);
    
    // ============ CONSTRUCTOR ============
    constructor(
        address _liquidityWallet,
        address _stakingWallet
    ) ERC20("NEXUS AI", "NEXUS") Ownable(msg.sender) {
        
        liquidityWallet = _liquidityWallet;
        stakingWallet = _stakingWallet;
        
        // Set limits
        maxWallet = TOTAL_SUPPLY * 2 / 100;  // 2%
        maxTx = TOTAL_SUPPLY * 1 / 100;      // 1%
        
        // Exclude from fees
        isExcludedFromFees[owner()] = true;
        isExcludedFromFees[address(this)] = true;
        isExcludedFromFees[liquidityWallet] = true;
        isExcludedFromFees[stakingWallet] = true;
        
        // Exclude from limits
        isExcludedFromLimits[owner()] = true;
        isExcludedFromLimits[address(this)] = true;
        isExcludedFromLimits[liquidityWallet] = true;
        isExcludedFromLimits[stakingWallet] = true;
        
        // Mint total supply to owner
        _mint(msg.sender, TOTAL_SUPPLY);
    }
    
    // ============ TRADING ============
    
    function enableTrading() external onlyOwner {
        require(!tradingEnabled, "Trading already enabled");
        tradingEnabled = true;
        launchBlock = block.number;
        emit TradingEnabled(block.number);
    }
    
    function removeLimits() external onlyOwner {
        limitsEnabled = false;
        maxWallet = TOTAL_SUPPLY;
        maxTx = TOTAL_SUPPLY;
        emit LimitsRemoved();
    }
    
    // ============ TRANSFER LOGIC ============
    
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal virtual override {
        
        // Skip for minting/burning
        if (from == address(0) || to == address(0)) {
            super._update(from, to, amount);
            return;
        }
        
        // Check blacklist
        require(!isBlacklisted[from] && !isBlacklisted[to], "Blacklisted");
        
        // Check trading enabled
        if (!tradingEnabled) {
            require(
                isExcludedFromFees[from] || isExcludedFromFees[to],
                "Trading not enabled"
            );
        }
        
        // Anti-bot: blacklist buys in first blocks
        if (
            tradingEnabled &&
            block.number <= launchBlock + deadBlocks &&
            isAMM[from] &&
            !isExcludedFromFees[to]
        ) {
            isBlacklisted[to] = true;
            emit BlacklistUpdated(to, true);
        }
        
        // Determine if buy/sell
        bool isBuy = isAMM[from];
        bool isSell = isAMM[to];
        
        // Check limits
        if (limitsEnabled && !isExcludedFromLimits[from] && !isExcludedFromLimits[to]) {
            
            // Max TX
            require(amount <= maxTx, "Exceeds max TX");
            
            // Max wallet (only on buys/transfers, not sells)
            if (!isSell) {
                require(
                    balanceOf(to) + amount <= maxWallet,
                    "Exceeds max wallet"
                );
            }
            
            // Sell cooldown
            if (isSell) {
                require(
                    block.timestamp >= lastSellTime[from] + sellCooldown,
                    "Sell cooldown active"
                );
                lastSellTime[from] = block.timestamp;
            }
        }
        
        // Calculate tax
        uint256 taxAmount = 0;
        
        if (!isExcludedFromFees[from] && !isExcludedFromFees[to]) {
            if (isBuy && buyTax > 0) {
                taxAmount = amount * buyTax / 100;
            } else if (isSell && sellTax > 0) {
                taxAmount = amount * sellTax / 100;
            } else if (!isBuy && !isSell && transferTax > 0) {
                taxAmount = amount * transferTax / 100;
            }
        }
        
        // Apply tax
        if (taxAmount > 0) {
            uint256 liquidityShare = taxAmount / 2;
            uint256 stakingShare = taxAmount - liquidityShare;
            
            // If selling, add burn
            if (isSell && sellTax > 0) {
                uint256 burnAmount = taxAmount / 3;
                stakingShare = stakingShare - burnAmount;
                super._update(from, burnAddress, burnAmount);
            }
            
            super._update(from, liquidityWallet, liquidityShare);
            super._update(from, stakingWallet, stakingShare);
            amount -= taxAmount;
        }
        
        super._update(from, to, amount);
    }
    
    // ============ ADMIN FUNCTIONS ============
    
    function setAMM(address pair, bool value) external onlyOwner {
        require(pair != address(0), "Zero address");
        isAMM[pair] = value;
        emit AMMUpdated(pair, value);
    }
    
    function setTaxes(uint256 _buyTax, uint256 _sellTax) external onlyOwner {
        require(_buyTax <= 10 && _sellTax <= 10, "Tax too high"); // Max 10%
        buyTax = _buyTax;
        sellTax = _sellTax;
        emit TaxesUpdated(_buyTax, _sellTax);
    }
    
    function setExcludedFromFees(address account, bool excluded) external onlyOwner {
        isExcludedFromFees[account] = excluded;
        emit ExcludedFromFees(account, excluded);
    }
    
    function setExcludedFromLimits(address account, bool excluded) external onlyOwner {
        isExcludedFromLimits[account] = excluded;
    }
    
    function setBlacklist(address account, bool blacklisted) external onlyOwner {
        require(account != owner(), "Cannot blacklist owner");
        isBlacklisted[account] = blacklisted;
        emit BlacklistUpdated(account, blacklisted);
    }
    
    function setWallets(address _liquidity, address _staking) external onlyOwner {
        require(_liquidity != address(0) && _staking != address(0), "Zero address");
        liquidityWallet = _liquidity;
        stakingWallet = _staking;
    }
    
    function setSellCooldown(uint256 _seconds) external onlyOwner {
        require(_seconds <= 1 days, "Cooldown too long");
        sellCooldown = _seconds;
    }
    
    function setLimits(uint256 _maxWallet, uint256 _maxTx) external onlyOwner {
        require(_maxWallet >= TOTAL_SUPPLY / 100, "Max wallet too low"); // Min 1%
        require(_maxTx >= TOTAL_SUPPLY / 200, "Max TX too low");         // Min 0.5%
        maxWallet = _maxWallet;
        maxTx = _maxTx;
    }
    
    // ============ EMERGENCY ============
    
    function rescueETH() external onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }
    
    function rescueTokens(address token) external onlyOwner {
        require(token != address(this), "Cannot rescue NEXUS");
        IERC20(token).transfer(owner(), IERC20(token).balanceOf(address(this)));
    }
    
    // ============ VIEW FUNCTIONS ============
    
    function getCirculatingSupply() public view returns (uint256) {
        return totalSupply() - balanceOf(burnAddress) - balanceOf(address(0));
    }
    
    function getBotTier(address account) public view returns (string memory) {
        uint256 balance = balanceOf(account);
        
        if (balance >= 1_000_000 * 10**18) return "DIAMOND";
        if (balance >= 200_000 * 10**18) return "GOLD";
        if (balance >= 50_000 * 10**18) return "SILVER";
        if (balance >= 10_000 * 10**18) return "BRONZE";
        return "FREE";
    }
    
    function getTierThreshold(string memory tier) public pure returns (uint256) {
        if (keccak256(bytes(tier)) == keccak256(bytes("DIAMOND"))) return 1_000_000 * 10**18;
        if (keccak256(bytes(tier)) == keccak256(bytes("GOLD"))) return 200_000 * 10**18;
        if (keccak256(bytes(tier)) == keccak256(bytes("SILVER"))) return 50_000 * 10**18;
        if (keccak256(bytes(tier)) == keccak256(bytes("BRONZE"))) return 10_000 * 10**18;
        return 0;
    }
    
    // Accept ETH
    receive() external payable {}
}
