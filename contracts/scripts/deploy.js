const hre = require("hardhat");

async function main() {
    console.log("==========================================");
    console.log("NEXUS AI TOKEN - DEPLOYMENT");
    console.log("==========================================");
    console.log(`Network: ${hre.network.name}`);
    console.log(`Chain ID: ${hre.network.config.chainId}`);
    console.log("");

    const [deployer] = await hre.ethers.getSigners();
    console.log("Deployer:", deployer.address);
    
    const balance = await hre.ethers.provider.getBalance(deployer.address);
    console.log("Balance:", hre.ethers.formatEther(balance), "ETH");
    console.log("");

    // ============ CONFIG ============
    // Use deployer as liquidity/staking wallet for simplicity
    // Change these in production!
    const liquidityWallet = process.env.LIQUIDITY_WALLET || deployer.address;
    const stakingWallet = process.env.STAKING_WALLET || deployer.address;

    console.log("Liquidity Wallet:", liquidityWallet);
    console.log("Staking Wallet:", stakingWallet);
    console.log("");

    // ============ DEPLOY TOKEN ============
    console.log("Deploying NexusToken...");
    
    const NexusToken = await hre.ethers.getContractFactory("NexusToken");
    const token = await NexusToken.deploy(liquidityWallet, stakingWallet);
    await token.waitForDeployment();
    
    const tokenAddress = await token.getAddress();
    console.log("✅ NexusToken deployed to:", tokenAddress);
    console.log("");

    // ============ DEPLOY STAKING ============
    console.log("Deploying NexusStaking...");
    
    const NexusStaking = await hre.ethers.getContractFactory("NexusStaking");
    const staking = await NexusStaking.deploy(tokenAddress);
    await staking.waitForDeployment();
    
    const stakingAddress = await staking.getAddress();
    console.log("✅ NexusStaking deployed to:", stakingAddress);
    console.log("");

    // ============ SETUP ============
    console.log("Setting up contracts...");
    
    // Exclude staking contract from fees
    await token.setExcludedFromFees(stakingAddress, true);
    console.log("✅ Staking contract excluded from fees");
    
    await token.setExcludedFromLimits(stakingAddress, true);
    console.log("✅ Staking contract excluded from limits");

    // ============ SUMMARY ============
    console.log("");
    console.log("==========================================");
    console.log("DEPLOYMENT COMPLETE!");
    console.log("==========================================");
    console.log("");
    console.log("Contracts:");
    console.log(`  NexusToken:   ${tokenAddress}`);
    console.log(`  NexusStaking: ${stakingAddress}`);
    console.log("");
    console.log("Next steps:");
    console.log("1. Verify contracts on block explorer");
    console.log("2. Add liquidity to DEX");
    console.log("3. Set AMM pair address: token.setAMM(pairAddress, true)");
    console.log("4. Enable trading: token.enableTrading()");
    console.log("5. Deposit rewards to staking: staking.depositRewards(amount)");
    console.log("");
    console.log("Verify commands:");
    console.log(`npx hardhat verify --network ${hre.network.name} ${tokenAddress} "${liquidityWallet}" "${stakingWallet}"`);
    console.log(`npx hardhat verify --network ${hre.network.name} ${stakingAddress} "${tokenAddress}"`);
    console.log("");

    // Save deployment info
    const deploymentInfo = {
        network: hre.network.name,
        chainId: hre.network.config.chainId,
        deployer: deployer.address,
        contracts: {
            NexusToken: tokenAddress,
            NexusStaking: stakingAddress
        },
        wallets: {
            liquidity: liquidityWallet,
            staking: stakingWallet
        },
        timestamp: new Date().toISOString()
    };

    const fs = require("fs");
    const filename = `deployments/${hre.network.name}.json`;
    
    if (!fs.existsSync("deployments")) {
        fs.mkdirSync("deployments");
    }
    
    fs.writeFileSync(filename, JSON.stringify(deploymentInfo, null, 2));
    console.log(`Deployment info saved to ${filename}`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
