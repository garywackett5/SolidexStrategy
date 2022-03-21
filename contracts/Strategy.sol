// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;
// WFTM-beFTM
// These are the core Yearn libraries
import {BaseStrategy, StrategyParams, VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";
import {SafeERC20, SafeMath, IERC20, Address} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";

interface ISolidlyRouter {
    function addLiquidity(
        address,
        address,
        bool,
        uint256,
        uint256,
        uint256,
        uint256,
        address,
        uint256
    )
        external
        returns (
            uint256 amountA,
            uint256 amountB,
            uint256 liquidity
        );

    function swapExactTokensForTokensSimple(
        uint256 amountIn,
        uint256 amountOutMin,
        address tokenFrom,
        address tokenTo,
        bool stable,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function removeLiquidity(
        address tokenA,
        address tokenB,
        bool stable,
        uint256 liquidity,
        uint256 amountAMin,
        uint256 amountBMin,
        address to,
        uint256 deadline
    ) external returns (uint256 amountA, uint256 amountB);

    function quoteRemoveLiquidity(
        address tokenA,
        address tokenB,
        bool stable,
        uint256 liquidity
    ) external view returns (uint256 amountA, uint256 amountB);

    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

interface IWrappedNative is IERC20 {
    function deposit() external payable;

    function withdraw(uint256 wad) external;
}

interface IZapbeFTM {
    function depositNative() external payable;
}

interface ILpDepositer {
    function deposit(address pool, uint256 _amount) external;

    function withdraw(address pool, uint256 _amount) external; // use amount = 0 for harvesting rewards

    function userBalances(address user, address pool)
        external
        view
        returns (uint256);

    function getReward(address[] memory lps) external;
}

interface ISpiritRouter {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

// the solidly stable and volatile duplicates is going to mess this up
interface IUniswapV2Router02 {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external
        view
        returns (uint256[] memory amounts);
}

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    /* ========== STATE VARIABLES ========== */

    // swap stuff
    address internal constant solidlyRouter =
        0xa38cd27185a464914D3046f0AB9d43356B34829D;
    address internal constant spiritRouter =
        0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52;
    bool public tradesEnabled;
    bool public realiseLosses;

    // tokens
    IWrappedNative internal constant wftm =
        IWrappedNative(0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83);
    IERC20 internal constant beftm =
        IERC20(0x7381eD41F6dE418DdE5e84B55590422a57917886);

    VaultAPI public yvault;

    uint256 public lpSlippage = 9990; //0.1% slippage allowance

    // 
    uint256 public beftmDiscount  = 9970;
    uint256 immutable DENOMINATOR = 10_000;

    uint256 public maxSell; //set to zero for unlimited

    bool public forceLosses;
    bool public useSpirit;

    string internal stratName; // we use this for our strategy's name on cloning
    address public lpToken =
        address(0x387a11D161f6855Bd3c801bA6C79Fe9b824Ce1f3); // StableV1 AMM - WFTM/beFTM

    address public lpTokenSpirit =
        address(0xE3D4C22d0543E050a8b3F713899854Ed792fc1bD); // Spirit LP - WFTM/beFTM

    IZapbeFTM public beftmMinter =
        IZapbeFTM(0x34753f36d69d00e2112Eb99B3F7f0FE76cC35090);

    bool internal forceHarvestTriggerOnce; // only set this to true externally when we want to trigger our keepers to harvest for us
    uint256 public minHarvestCredit; // if we hit this amount of credit, harvest the strategy

    /* ========== CONSTRUCTOR ========== */
    receive() external payable {}

    constructor(
        address _vault,
        string memory _name,
        address _beftmYvault
    ) public BaseStrategy(_vault) {
        _initializeStrat(_name, _beftmYvault);
    }

    /* ========== CLONING ========== */

    event Cloned(address indexed clone);

    // this is called by our original strategy, as well as any clones
    function _initializeStrat(string memory _name, address _beftmYvault)
        internal
    {
        // initialize variables
        maxReportDelay = 43200; // 1/2 day in seconds, if we hit this then harvestTrigger = True
        healthCheck = address(0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0); // Fantom common health check

        yvault = VaultAPI(_beftmYvault);

        require(yvault.token() == address(beftm));

        // set our strategy's name
        stratName = _name;
        maxSell = 500_000 * 1e18;

        // turn off our credit harvest trigger to start with
        minHarvestCredit = type(uint256).max;

        beftm.approve(address(solidlyRouter), type(uint256).max);
        wftm.approve(address(solidlyRouter), type(uint256).max);
        beftm.approve(address(spiritRouter), type(uint256).max);
        wftm.approve(address(spiritRouter), type(uint256).max);
        beftm.approve(address(_beftmYvault), type(uint256).max);
    }

    /* ========== VIEWS ========== */

    function name() external view override returns (string memory) {
        return stratName;
    }

    // balance of wftm in strat - should be zero most of the time
    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    function balanceOfBeftm() public view returns (uint256) {
        return beftm.balanceOf(address(this));
    }

    // should be worth 1:1 but there are swap fees to consider when exiting back in wftm (beftmDiscount)
    // spirit = 0.3% fee
    // solid = 0.01% fee
    function balanceOfBeftmInWant(uint256 beftmAmount)
        public
        view
        returns (uint256)
    {
        return beftmAmount.mul(beftmDiscount).div(DENOMINATOR);
    }

    function balanceOfyVault() public view returns (uint256) {
        return yvault.balanceOf(address(this));
    }

    function balanceOfyVaultInBeftm() public view returns (uint256) {
        return yvaultToBeftm(balanceOfyVault());
    }

    function yvaultToBeftm(uint256 _vaultTokens) public view returns (uint256) {
        uint256 pps = yvault.pricePerShare();
        uint256 inWant = _vaultTokens.mul(pps).div(10**yvault.decimals());
        return inWant;
    }

    function beftmToYvault(uint256 _beftmAmount) public view returns (uint256) {
        uint256 pps = yvault.pricePerShare();
        uint256 inWant = _beftmAmount.mul(10**yvault.decimals()).div(pps);
        return inWant;
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        uint256 _balanceOfyVaultInBeftm = balanceOfyVaultInBeftm();

        uint256 balanceOfBeftmInWftm = balanceOfBeftmInWant(
            _balanceOfyVaultInBeftm.add(balanceOfBeftm())
        );

        // look at our staked tokens and any free tokens sitting in the strategy
        return balanceOfBeftmInWftm.add(balanceOfWant());
    }

    function delegatedAssets() public view override returns (uint256) {
        return vault.strategies(address(this)).totalDebt;
    }

    /* ========== MUTATIVE FUNCTIONS ========== */

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        uint256 assets = estimatedTotalAssets();
        uint256 wantBal = balanceOfWant();

        uint256 debt = vault.strategies(address(this)).totalDebt;
        uint256 amountToFree;

        if (assets >= debt) {
            _debtPayment = _debtOutstanding;
            _profit = assets.sub(debt);

            amountToFree = _profit.add(_debtPayment);
        } else {
            //loss should never happen. so leave blank. lets not record if so and handle manually
            //dont withdraw either incase we realise losses
            //withdraw with loss
            if (realiseLosses) {
                _loss = debt.sub(assets);
                if (_debtOutstanding > _loss) {
                    _debtPayment = _debtOutstanding.sub(_loss);
                } else {
                    _debtPayment = 0;
                }

                amountToFree = _debtPayment;
            }
        }

        //amountToFree > 0 checking (included in the if statement)
        if (wantBal < amountToFree) {
            (, uint256 swapLoss) = liquidatePosition(amountToFree);
            if (_profit > 0) {
                //reduce our profit by whatever we lost swapping some money out
                if (_profit > swapLoss) {
                    _profit = _profit - swapLoss;
                    swapLoss = 0;
                } else {
                    _profit = 0;
                    swapLoss = swapLoss - _profit;
                }
            }
            _loss = swapLoss.add(_loss);

            uint256 newLoose = want.balanceOf(address(this));

            //if we dont have enough money adjust _debtOutstanding and only change profit if needed
            if (newLoose < amountToFree) {
                if (_profit > newLoose) {
                    _profit = newLoose;
                    _debtPayment = 0;
                } else {
                    _debtPayment = Math.min(newLoose - _profit, _debtPayment);
                }
            }
        }

        // we're done harvesting, so reset our trigger if we used it
        forceHarvestTriggerOnce = false;
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }
        // send all of our want tokens to be deposited
        uint256 toInvest = balanceOfWant();

        if (toInvest > 1e17) {
            wftm.withdraw(toInvest);

            beftmMinter.depositNative{value: address(this).balance}();

            wftm.deposit{value: address(this).balance}();
        }

        uint256 beftmBalance = balanceOfBeftm();

        if (beftmBalance > 0) {
            yvault.deposit();
        }
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 balanceOfWftm = want.balanceOf(address(this));

        // if we need more wftm than is already loose in the contract
        if (balanceOfWftm < _amountNeeded) {
            // wftm needed beyond any wftm that is already loose in the contract
            uint256 amountToFree = _amountNeeded.sub(balanceOfWftm);

            // converts this amount into lpTokens
            //lets assume we can get 1-1 and treat any extra as loss

            uint256 _balanceOfBeftm = balanceOfBeftm();

            if (_balanceOfBeftm < amountToFree) {
                uint256 balOfYv = balanceOfyVault();

                uint256 toWithdrawFromYvault = Math.min(
                    beftmToYvault(amountToFree - _balanceOfBeftm),
                    balOfYv
                );

                //need to withdraw from yvault
                yvault.withdraw(toWithdrawFromYvault);

                //note we can not get all we ask for from vault
                _balanceOfBeftm = balanceOfBeftm();
            }

            //should be 1-1
            uint256 wftm_change = balanceOfWant();
            _sell(Math.min(_balanceOfBeftm, amountToFree));
            uint256 beftm_change = _balanceOfBeftm.sub(balanceOfBeftm());
            wftm_change = balanceOfWant() - wftm_change;

            //our loss is the difference between beftm change and wftmchange
            if (beftm_change > wftm_change) {
                _loss = beftm_change - wftm_change;
            }

            _liquidatedAmount = Math.min(
                want.balanceOf(address(this)),
                _amountNeeded
            );
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function liquidateAllPositions() internal override returns (uint256) {
        yvault.withdraw();

        _sell(balanceOfBeftm());

        if (!forceLosses) {
            require(balanceOfBeftm() == 0, "couldnt liquidate all beftm");
        }

        return balanceOfWant();
    }

    function prepareMigration(address _newStrategy) internal override {
        uint256 yvBalance = balanceOfyVault();

        if (yvBalance > 0) {
            //send all our yvtokens to new strat
            IERC20(address(yvault)).safeTransfer(_newStrategy, yvBalance);
        }

        uint256 beftmBalance = balanceOfBeftm();

        if (beftmBalance > 0) {
            // send our total balance of beftm to the new strategy
            beftm.transfer(_newStrategy, beftmBalance);
        }
    }

    function manualSell(uint256 _amount) external onlyEmergencyAuthorized {
        _sell(_amount);
    }

    // sell from beftm to want
    function _sell(uint256 _amount) internal {
        if (maxSell > 0) {
            _amount = Math.min(maxSell, _amount);
        }

        // sell our beftm for wftm
        address[] memory beftmTokenPath = new address[](2);
        beftmTokenPath[0] = address(beftm);
        beftmTokenPath[1] = address(wftm);

        if (useSpirit) {
            IUniswapV2Router02(spiritRouter).swapExactTokensForTokens(
                _amount,
                _amount.mul(lpSlippage).div(DENOMINATOR),
                beftmTokenPath,
                address(this),
                block.timestamp
            );
        } else {
            ISolidlyRouter(solidlyRouter).swapExactTokensForTokensSimple(
                _amount,
                _amount.mul(lpSlippage).div(DENOMINATOR),
                address(beftm),
                address(wftm),
                true,
                address(this),
                block.timestamp
            );
        }
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    // our main trigger is regarding our DCA since there is low liquidity for our "emissionToken"
    function harvestTrigger(uint256 callCostinEth)
        public
        view
        override
        returns (bool)
    {
        StrategyParams memory params = vault.strategies(address(this));

        // harvest no matter what once we reach our maxDelay
        if (block.timestamp.sub(params.lastReport) > maxReportDelay) {
            return true;
        }

        // trigger if we want to manually harvest
        if (forceHarvestTriggerOnce) {
            return true;
        }

        // trigger if we have enough credit
        if (vault.creditAvailable() >= minHarvestCredit) {
            return true;
        }

        // otherwise, we don't harvest
        return false;
    }

    function ethToWant(uint256 _amtInWei)
        public
        view
        override
        returns (uint256)
    {}

    /* ========== SETTERS ========== */

    ///@notice This allows us to manually harvest with our keeper as needed
    function setForceHarvestTriggerOnce(bool _forceHarvestTriggerOnce)
        external
        onlyEmergencyAuthorized
    {
        forceHarvestTriggerOnce = _forceHarvestTriggerOnce;
    }

    ///@notice When our strategy has this much credit, harvestTrigger will be true.
    function setMinHarvestCredit(uint256 _minHarvestCredit)
        external
        onlyEmergencyAuthorized
    {
        minHarvestCredit = _minHarvestCredit;
    }

    function setRealiseLosses(bool _realiseLoosses) external onlyVaultManagers {
        realiseLosses = _realiseLoosses;
    }

    // onlyGovernance can set high slippage
    function setLpSlippage(uint256 _slippage, bool _force)
        external
        onlyGovernance
    {
        _setLpSlippage(_slippage, _force);
    }

    // only vault managers can set slippage
    function setLpSlippage(uint256 _slippage) external onlyEmergencyAuthorized {
        _setLpSlippage(_slippage, false);
    }

    function _setLpSlippage(uint256 _slippage, bool _force) internal {
        require(_slippage <= DENOMINATOR, "higher than max");
        if (!_force) {
            require(_slippage >= 9900, "higher than 1pc slippage set");
        }
        lpSlippage = _slippage;
    }

    // beftm should be worth 1:1 with wftm, but there are swap fees to consider when exiting (beftmDiscount) 
    // beftmDiscount is used in estimatedTotalAssets
    // set a max sell for illiquid pools
    function setBeftmDiscount(uint256 _beftmDiscount) external onlyGovernance {
        beftmDiscount = _beftmDiscount;
    }

    // set a max sell for illiquid pools
    function setMaxSell(uint256 _maxSell) external onlyEmergencyAuthorized {
        maxSell = _maxSell;
    }

    function setUseSpirit(bool _useSpirit) external onlyEmergencyAuthorized {
        useSpirit = _useSpirit;
    }
}
