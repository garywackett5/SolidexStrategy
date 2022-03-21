import brownie
from brownie import chain, Contract
import math

# lower debtRatio to 50%, donate, withdraw less than the donation, then harvest
def test_withdraw_after_donation_1(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    currentDebt = vault.strategies(strategy)[2]
    vault.updateStrategyDebtRatio(strategy, currentDebt / 2, {"from": gov})
    assert vault.strategies(strategy)[2] == 5000

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraw half of his donation, this ensures that we test withdrawing without pulling from the staked balance
    vault.withdraw(donation / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check to make sure that our debtRatio is about half of our previous debt
    assert new_params["debtRatio"] == currentDebt / 2

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# lower debtRatio to 0, donate, withdraw less than the donation, then harvest
def test_withdraw_after_donation_2(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    currentDebt = vault.strategies(strategy)[2]
    vault.updateStrategyDebtRatio(strategy, 0, {"from": gov})
    assert vault.strategies(strategy)[2] == 0

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraw half of his donation, this ensures that we test withdrawing without pulling from the staked balance
    vault.withdraw(donation / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# lower debtRatio to 0, donate, withdraw more than the donation, then harvest
def test_withdraw_after_donation_3(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    currentDebt = vault.strategies(strategy)[2]
    vault.updateStrategyDebtRatio(strategy, 0, {"from": gov})
    assert vault.strategies(strategy)[2] == 0

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    vault.withdraw(donation + amount / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# lower debtRatio to 50%, donate, withdraw more than the donation, then harvest
def test_withdraw_after_donation_4(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    currentDebt = vault.strategies(strategy)[2]
    vault.updateStrategyDebtRatio(strategy, currentDebt / 2, {"from": gov})
    assert vault.strategies(strategy)[2] == 5000

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    vault.withdraw(donation + amount / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params[
        "totalGain"
    ] > donation or math.isclose(
        new_params["totalGain"] - prev_params["totalGain"], donation, abs_tol=5
    )

    # check to make sure that our debtRatio is about half of our previous debt
    assert new_params["debtRatio"] == currentDebt / 2

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# donate, withdraw more than the donation, then harvest
def test_withdraw_after_donation_5(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    vault.withdraw(donation + amount / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# donate, withdraw less than the donation, then harvest
def test_withdraw_after_donation_6(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    vault.withdraw(donation / 2, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    new_params = vault.strategies(strategy).dict()

    # sleep 10 hours to increase our credit available for last assert at the bottom.
    chain.sleep(60 * 60 * 10)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )

    # assert that our vault total assets, multiplied by our debtRatio, is about equal to our estimated total assets plus credit available (within 1 token)
    # we multiply this by the debtRatio of our strategy out of 10_000 total
    # we sleep 10 hours above specifically for this check
    assert math.isclose(
        vault.totalAssets() * new_params["debtRatio"] / 10_000,
        strategy.estimatedTotalAssets() + vault.creditAvailable(strategy),
        abs_tol=1e18,
    )


# lower debtRatio to 0, donate, withdraw more than the donation, then harvest
def test_withdraw_after_donation_7(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()
    prev_assets = vault.totalAssets()

    currentDebt = vault.strategies(strategy)[2]
    vault.updateStrategyDebtRatio(strategy, 0, {"from": gov})
    assert vault.strategies(strategy)[2] == 0

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    withdrawal = donation + amount / 2
    vault.withdraw(withdrawal, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # We harvest twice to take profits and then to send the funds to our strategy. This is for our last check below.
    chain.sleep(1)

    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})

    # check everywhere to make sure we emptied out the strategy and ignore dust
    assert strategy.estimatedTotalAssets() <= 100
    assert token.balanceOf(strategy) == 0
    current_assets = vault.totalAssets()

    # assert that our total assets have gone up or stayed the same when accounting for the donation and withdrawal
    assert current_assets >= donation - withdrawal + prev_assets

    new_params = vault.strategies(strategy).dict()

    # assert that our strategy has no debt
    assert new_params["totalDebt"] <= 100
    assert vault.totalDebt() <= 100

    # sleep to allow share price to normalize
    chain.sleep(86400)
    chain.mine(1)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )


# lower debtRatio to 0, donate, withdraw more than the donation, then harvest
def test_withdraw_after_donation_8(
    gov,
    token,
    vault,
    strategist,
    whale,
    strategy,
    chain,
    amount,
):

    ## deposit to the vault after approving
    token.approve(vault, 2 ** 256 - 1, {"from": whale})
    vault.deposit(amount, {"from": whale})
    chain.sleep(1)
    strategy.setDoHealthCheck(False, {"from": gov})
    strategy.harvest({"from": gov})
    chain.sleep(1)

    prev_params = vault.strategies(strategy).dict()
    prev_assets = vault.totalAssets()

    vault.updateStrategyDebtRatio(strategy, 0, {"from": gov})
    assert vault.strategies(strategy)[2] == 0

    # under our new method of using min and maxDelay, this no longer matters or works
    # tx = new_strategy.harvestTrigger(0, {"from": gov})
    # print("\nShould we harvest? Should be true.", tx)
    # assert tx == True

    # our whale donates dust to the vault, what a nice person!
    donation = amount / 2
    token.transfer(strategy, donation, {"from": whale})

    # have our whale withdraws more than his donation, ensuring we pull from strategy
    withdrawal = donation / 2
    vault.withdraw(withdrawal, {"from": whale})

    # simulate one day of earnings
    chain.sleep(86400)
    chain.mine(1)

    # We harvest twice to take profits and then to send the funds to our strategy. This is for our last check below.
    chain.sleep(1)
    print(strategy.estimatedTotalAssets()/1e18)
    # turn off health check since we just took big profit
    strategy.setDoHealthCheck(False, {"from": gov})
    t1=strategy.harvest({"from": gov})
    print(t1.events["Harvested"])
    print(strategy.estimatedTotalAssets()/1e18)
    # have to do a second harvest to remove the 0.3% that was remaining
    # it's actually 0.29% (0.30% - 0.01%)
    strategy.setDoHealthCheck(False, {"from": gov})
    t1=strategy.harvest({"from": gov})
    print(t1.events["Harvested"])
    print(strategy.estimatedTotalAssets()/1e18)
    # check everywhere to make sure we emptied out the strategy
    # 0.29% of the 0.29% is still in the strategy
    assert strategy.estimatedTotalAssets() <= 1 * 1e18
    assert token.balanceOf(strategy) == 0
    current_assets = vault.totalAssets()

    beftmDiscount = strategy.beftmDiscount()

    # assert that our total assets have gone up or stayed the same when accounting for the donation and withdrawal
    assert current_assets >= donation - withdrawal + prev_assets - (0.0035*amount/2) - (amount*(10_000-beftmDiscount)/10_000)

    new_params = vault.strategies(strategy).dict()

    # assert that our strategy has no debt
    assert new_params["totalDebt"] <= 100
    assert vault.totalDebt() <= 100

    # sleep to allow share price to normalize
    chain.sleep(86400)
    chain.mine(1)

    profit = new_params["totalGain"] - prev_params["totalGain"]

    # check that we've recorded a gain
    assert profit > 0

    # specifically check that our gain is greater than our donation or confirm we're no more than 5 wei off.
    assert new_params["totalGain"] - prev_params["totalGain"] > donation  - (0.0035*amount/2) - (amount*(10_000-beftmDiscount)/10_000)

    # check that we didn't add any more loss, or at least no more than 2 wei
    assert new_params["totalLoss"] == prev_params["totalLoss"] or math.isclose(
        new_params["totalLoss"], prev_params["totalLoss"], abs_tol=2
    )
