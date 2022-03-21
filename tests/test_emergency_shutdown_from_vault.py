import brownie
from brownie import Contract
from brownie import config
import math

# test passes as of 21-06-26
def test_emergency_shutdown_from_vault(
    gov,
    token,
    vault,
    whale,
    strategy,
    chain,
    amount,
):
    ## deposit to the vault after approving
    startingWhale = token.balanceOf(whale)
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    # simulate one day of earnings
    chain.sleep(86400)

    chain.mine(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})

    # simulate one day of earnings
    chain.sleep(86400)

    # set emergency and exit, then confirm that the strategy has no funds
    vault.setEmergencyShutdown(True, {"from": gov})
    strategy.setRealiseLosses(True, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    t1 = strategy.harvest({"from": gov})
    print(t1.events["Harvested"])
    print(strategy.estimatedTotalAssets()/1e18)
    chain.sleep(1)
    # have to do a second harvest to remove the 0.3% that was remaining
    # it's actually 0.29% (0.30% - 0.01%)
    strategy.setDoHealthCheck(False, {"from": gov})
    t1 = strategy.harvest({"from": gov})
    print(t1.events["Harvested"])
    print(strategy.estimatedTotalAssets()/1e18)
    chain.sleep(1)
    assert strategy.estimatedTotalAssets() <= 1 * 1e18
    assert token.balanceOf(strategy) == 0

    # simulate a day of waiting for share price to bump back up
    chain.sleep(86400)
    chain.mine(1)

    # withdraw and confirm we made money
    vault.withdraw({"from": whale})
    assert token.balanceOf(whale) >= startingWhale or math.isclose(
        token.balanceOf(whale), startingWhale, abs_tol=5
    )
