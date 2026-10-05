// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/// @title TallyInvoices
/// @notice Payment links for USDC and EURC on Arc.
/// A merchant creates an invoice, the buyer pays it with one transaction,
/// and the funds go straight to the merchant. The contract never holds money.
///
/// On Arc, USDC is the native gas token, so a USDC invoice is paid with
/// msg.value (18 decimals) and needs no approve. Any other token (EURC)
/// is pulled with transferFrom after an approve.
contract TallyInvoices {
    /// @dev token == NATIVE_USDC means the invoice is paid in native USDC.
    address public constant NATIVE_USDC = address(0);

    uint256 public constant MAX_MEMO_BYTES = 140;

    enum Status {
        None,
        Open,
        Paid,
        Cancelled
    }

    struct Invoice {
        address merchant;
        address token;
        uint256 amount;
        Status status;
        address payer;
        uint64 createdAt;
        uint64 paidAt;
        string memo;
    }

    uint256 public invoiceCount;
    mapping(uint256 => Invoice) private _invoices;

    event InvoiceCreated(
        uint256 indexed id, address indexed merchant, address token, uint256 amount, string memo
    );
    event InvoicePaid(
        uint256 indexed id, address indexed payer, address indexed merchant, address token, uint256 amount
    );
    event InvoiceCancelled(uint256 indexed id);

    error ZeroAmount();
    error MemoTooLong();
    error NotOpen();
    error NotMerchant();
    error WrongValue();
    error NativeTransferFailed();
    error TokenTransferFailed();
    error NotAToken();

    /// @notice Create an invoice payable to msg.sender.
    /// @param token NATIVE_USDC for USDC, or an ERC-20 address such as EURC.
    /// @param amount In the token's own units (18 decimals for native USDC).
    function createInvoice(address token, uint256 amount, string calldata memo)
        external
        returns (uint256 id)
    {
        if (amount == 0) revert ZeroAmount();
        if (bytes(memo).length > MAX_MEMO_BYTES) revert MemoTooLong();
        // A token address without code would let transferFrom "succeed" with no funds moved.
        if (token != NATIVE_USDC && token.code.length == 0) revert NotAToken();

        id = ++invoiceCount;
        _invoices[id] = Invoice({
            merchant: msg.sender,
            token: token,
            amount: amount,
            status: Status.Open,
            payer: address(0),
            createdAt: uint64(block.timestamp),
            paidAt: 0,
            memo: memo
        });

        emit InvoiceCreated(id, msg.sender, token, amount, memo);
    }

    /// @notice Pay an open invoice. Funds go directly to the merchant.
    function pay(uint256 id) external payable {
        Invoice storage inv = _invoices[id];
        if (inv.status != Status.Open) revert NotOpen();

        // Effects before interactions: a re-entrant call sees the invoice as paid.
        inv.status = Status.Paid;
        inv.payer = msg.sender;
        inv.paidAt = uint64(block.timestamp);

        if (inv.token == NATIVE_USDC) {
            if (msg.value != inv.amount) revert WrongValue();
            (bool ok,) = inv.merchant.call{value: msg.value}("");
            if (!ok) revert NativeTransferFailed();
        } else {
            if (msg.value != 0) revert WrongValue();
            _pullToken(inv.token, msg.sender, inv.merchant, inv.amount);
        }

        emit InvoicePaid(id, msg.sender, inv.merchant, inv.token, inv.amount);
    }

    /// @notice The merchant can cancel an invoice that has not been paid.
    function cancel(uint256 id) external {
        Invoice storage inv = _invoices[id];
        if (inv.status != Status.Open) revert NotOpen();
        if (inv.merchant != msg.sender) revert NotMerchant();
        inv.status = Status.Cancelled;
        emit InvoiceCancelled(id);
    }

    function getInvoice(uint256 id) external view returns (Invoice memory) {
        return _invoices[id];
    }

    /// @dev Accepts tokens that return true, and tokens that return nothing.
    function _pullToken(address token, address from, address to, uint256 amount) private {
        (bool ok, bytes memory data) =
            token.call(abi.encodeWithSelector(0x23b872dd, from, to, amount));
        if (!ok || (data.length != 0 && !abi.decode(data, (bool)))) revert TokenTransferFailed();
    }
}
