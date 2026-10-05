// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

import {Test} from "forge-std/Test.sol";
import {TallyInvoices} from "../src/TallyInvoices.sol";

contract MockToken {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        if (allowance[from][msg.sender] < amount || balanceOf[from] < amount) return false;
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract RejectsEther {
    function create(TallyInvoices t, uint256 amount) external returns (uint256) {
        return t.createInvoice(address(0), amount, "rejects");
    }
}

contract Reenterer {
    TallyInvoices public t;
    uint256 public target;

    function setup(TallyInvoices _t, uint256 amount) external returns (uint256 id) {
        t = _t;
        id = t.createInvoice(address(0), amount, "reenter");
        target = id;
    }

    receive() external payable {
        // Try to pay the same invoice again from inside the payout.
        t.pay{value: msg.value}(target);
    }
}

contract TallyInvoicesTest is Test {
    TallyInvoices t;
    MockToken eurc;
    address merchant = makeAddr("merchant");
    address buyer = makeAddr("buyer");

    function setUp() public {
        t = new TallyInvoices();
        eurc = new MockToken();
        vm.deal(buyer, 100 ether);
    }

    function test_nativeInvoiceForwardsFundsToMerchant() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(0), 5 ether, "coffee beans");

        vm.prank(buyer);
        t.pay{value: 5 ether}(id);

        assertEq(merchant.balance, 5 ether);
        assertEq(address(t).balance, 0);
        TallyInvoices.Invoice memory inv = t.getInvoice(id);
        assertEq(uint8(inv.status), uint8(TallyInvoices.Status.Paid));
        assertEq(inv.payer, buyer);
    }

    function test_wrongValueReverts() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(0), 5 ether, "x");
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.WrongValue.selector);
        t.pay{value: 4 ether}(id);
    }

    function test_cannotPayTwice() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(0), 1 ether, "x");
        vm.startPrank(buyer);
        t.pay{value: 1 ether}(id);
        vm.expectRevert(TallyInvoices.NotOpen.selector);
        t.pay{value: 1 ether}(id);
        vm.stopPrank();
    }

    function test_unknownInvoiceReverts() public {
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.NotOpen.selector);
        t.pay{value: 1 ether}(42);
    }

    function test_tokenInvoicePullsFromBuyer() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(eurc), 20e6, "design work");
        eurc.mint(buyer, 50e6);

        vm.startPrank(buyer);
        eurc.approve(address(t), 20e6);
        t.pay(id);
        vm.stopPrank();

        assertEq(eurc.balanceOf(merchant), 20e6);
        assertEq(eurc.balanceOf(buyer), 30e6);
    }

    function test_tokenInvoiceWithoutApproveReverts() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(eurc), 20e6, "x");
        eurc.mint(buyer, 50e6);
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.TokenTransferFailed.selector);
        t.pay(id);
        assertEq(uint8(t.getInvoice(id).status), uint8(TallyInvoices.Status.Open));
    }

    function test_tokenInvoiceRejectsValue() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(eurc), 20e6, "x");
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.WrongValue.selector);
        t.pay{value: 1}(id);
    }

    function test_tokenWithoutCodeIsRejected() public {
        vm.prank(merchant);
        vm.expectRevert(TallyInvoices.NotAToken.selector);
        t.createInvoice(makeAddr("eoa"), 1, "x");
    }

    function test_onlyMerchantCanCancel() public {
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(0), 1 ether, "x");
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.NotMerchant.selector);
        t.cancel(id);

        vm.prank(merchant);
        t.cancel(id);
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.NotOpen.selector);
        t.pay{value: 1 ether}(id);
    }

    function test_zeroAmountAndLongMemoRevert() public {
        vm.expectRevert(TallyInvoices.ZeroAmount.selector);
        t.createInvoice(address(0), 0, "x");
        vm.expectRevert(TallyInvoices.MemoTooLong.selector);
        t.createInvoice(address(0), 1, string(new bytes(141)));
    }

    function test_merchantThatRejectsEtherMakesPaymentRevert() public {
        RejectsEther m = new RejectsEther();
        uint256 id = m.create(t, 1 ether);
        vm.prank(buyer);
        vm.expectRevert(TallyInvoices.NativeTransferFailed.selector);
        t.pay{value: 1 ether}(id);
        assertEq(uint8(t.getInvoice(id).status), uint8(TallyInvoices.Status.Open));
        assertEq(buyer.balance, 100 ether);
    }

    function test_reentrantPayIsBlocked() public {
        Reenterer r = new Reenterer();
        uint256 id = r.setup(t, 1 ether);
        vm.prank(buyer);
        // The inner pay sees the invoice as Paid and reverts, which fails the payout.
        vm.expectRevert(TallyInvoices.NativeTransferFailed.selector);
        t.pay{value: 1 ether}(id);
    }

    function testFuzz_nativeAmountExact(uint96 amount) public {
        vm.assume(amount > 0 && amount <= 100 ether);
        vm.prank(merchant);
        uint256 id = t.createInvoice(address(0), amount, "fuzz");
        vm.prank(buyer);
        t.pay{value: amount}(id);
        assertEq(merchant.balance, amount);
    }
}
