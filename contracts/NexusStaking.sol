// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * NEXUS AI - Staking Contract
 * Stake $NEXUS → Earn rewards → Higher bot tier
 */

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract NexusStaking is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;
    
    // ============ STATE ============
    IERC20 public nexusToken;
    
    uint256 public rewardRate = 100;        // 100 = 10% APY base
    uint256 public constant RATE_PRECISION = 1000;
    uint256 public totalStaked;
    
    uint256 public minStakeDuration = 7 days;
    uint256 public earlyWithdrawPenalty = 10; // 10%
    
    // ============ STRUCTS ============
    struct StakeInfo {
        uint256 amount;
        uint256 startTime;
        uint256 lastClaimTime;
        uint256 pendingRewards;
    }
    
    mapping(address => StakeInfo) public stakes;
    
    // ============ EVENTS ============
    event Staked(address indexed user, uint256 amount);
    event Unstaked(address indexed user, uint256 amount, uint256 penalty);
    event RewardsClaimed(address indexed user, uint256 amount);
    event RewardRateUpdated(uint256 newRate);
    
    // ============ CONSTRUCTOR ============
    constructor(address _nexusToken) Ownable(msg.sender) {
        nexusToken = IERC20(_nexusToken);
    }
    
    // ============ STAKING ============
    
    function stake(uint256 amount) external nonReentrant {
        require(amount > 0, "Cannot stake 0");
        
        // Update pending rewards before modifying stake
        _updateRewards(msg.sender);
        
        // Transfer tokens
        nexusToken.safeTransferFrom(msg.sender, address(this), amount);
        
        // Update stake
        stakes[msg.sender].amount += amount;
        stakes[msg.sender].startTime = block.timestamp;
        
        totalStaked += amount;
        
        emit Staked(msg.sender, amount);
    }
    
    function unstake(uint256 amount) external nonReentrant {
        StakeInfo storage userStake = stakes[msg.sender];
        require(userStake.amount >= amount, "Insufficient stake");
        require(amount > 0, "Cannot unstake 0");
        
        // Update pending rewards
        _updateRewards(msg.sender);
        
        uint256 penalty = 0;
        uint256 toTransfer = amount;
        
        // Early withdraw penalty
        if (block.timestamp < userStake.startTime + minStakeDuration) {
            penalty = amount * earlyWithdrawPenalty / 100;
            toTransfer = amount - penalty;
        }
        
        // Update stake
        userStake.amount -= amount;
        totalStaked -= amount;
        
        // Transfer tokens (minus penalty)
        nexusToken.safeTransfer(msg.sender, toTransfer);
        
        // Penalty goes to contract (for future rewards)
        
        emit Unstaked(msg.sender, amount, penalty);
    }
    
    function claimRewards() external nonReentrant {
        _updateRewards(msg.sender);
        
        uint256 rewards = stakes[msg.sender].pendingRewards;
        require(rewards > 0, "No rewards");
        
        stakes[msg.sender].pendingRewards = 0;
        
        // Transfer rewards
        nexusToken.safeTransfer(msg.sender, rewards);
        
        emit RewardsClaimed(msg.sender, rewards);
    }
    
    function compoundRewards() external nonReentrant {
        _updateRewards(msg.sender);
        
        uint256 rewards = stakes[msg.sender].pendingRewards;
        require(rewards > 0, "No rewards");
        
        stakes[msg.sender].pendingRewards = 0;
        stakes[msg.sender].amount += rewards;
        totalStaked += rewards;
        
        emit Staked(msg.sender, rewards);
    }
    
    // ============ INTERNAL ============
    
    function _updateRewards(address user) internal {
        StakeInfo storage userStake = stakes[user];
        
        if (userStake.amount == 0) {
            userStake.lastClaimTime = block.timestamp;
            return;
        }
        
        uint256 timeElapsed = block.timestamp - userStake.lastClaimTime;
        uint256 rewards = userStake.amount * rewardRate * timeElapsed / (365 days * RATE_PRECISION);
        
        userStake.pendingRewards += rewards;
        userStake.lastClaimTime = block.timestamp;
    }
    
    // ============ VIEW ============
    
    function getStakeInfo(address user) external view returns (
        uint256 stakedAmount,
        uint256 pendingRewards,
        uint256 stakeDuration,
        bool canWithdrawWithoutPenalty,
        string memory tier
    ) {
        StakeInfo memory userStake = stakes[user];
        
        stakedAmount = userStake.amount;
        stakeDuration = block.timestamp - userStake.startTime;
        canWithdrawWithoutPenalty = stakeDuration >= minStakeDuration;
        
        // Calculate pending (including unclaimed)
        if (userStake.amount > 0) {
            uint256 timeElapsed = block.timestamp - userStake.lastClaimTime;
            uint256 newRewards = userStake.amount * rewardRate * timeElapsed / (365 days * RATE_PRECISION);
            pendingRewards = userStake.pendingRewards + newRewards;
        }
        
        // Tier based on staked amount
        if (stakedAmount >= 1_000_000 * 10**18) tier = "DIAMOND";
        else if (stakedAmount >= 200_000 * 10**18) tier = "GOLD";
        else if (stakedAmount >= 50_000 * 10**18) tier = "SILVER";
        else if (stakedAmount >= 10_000 * 10**18) tier = "BRONZE";
        else tier = "FREE";
    }
    
    function getAPY() external view returns (uint256) {
        return rewardRate * 100 / RATE_PRECISION; // Returns percentage
    }
    
    // ============ ADMIN ============
    
    function setRewardRate(uint256 _rate) external onlyOwner {
        require(_rate <= 500, "Rate too high"); // Max 50% APY
        rewardRate = _rate;
        emit RewardRateUpdated(_rate);
    }
    
    function setMinStakeDuration(uint256 _duration) external onlyOwner {
        require(_duration <= 30 days, "Duration too long");
        minStakeDuration = _duration;
    }
    
    function setEarlyWithdrawPenalty(uint256 _penalty) external onlyOwner {
        require(_penalty <= 25, "Penalty too high");
        earlyWithdrawPenalty = _penalty;
    }
    
    function depositRewards(uint256 amount) external onlyOwner {
        nexusToken.safeTransferFrom(msg.sender, address(this), amount);
    }
    
    function rescueTokens(address token) external onlyOwner {
        require(token != address(nexusToken), "Cannot rescue staking token");
        IERC20(token).safeTransfer(owner(), IERC20(token).balanceOf(address(this)));
    }
}
