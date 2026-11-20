#include "hybrid_quant/core.hpp"

#include <algorithm>
#include <cmath>
#include <new>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace {
bool valid(double x) { return std::isfinite(x) && x > 0.0; }

struct Position {
    long long quantity = 0;
    double average_cost = 0.0;  // includes allocated entry commission
};

struct PendingOrder {
    long long id = 0;
    std::string symbol;
    int side = 0;
    long long remaining = 0;
    double limit_price = 0.0;
};

struct FillEvent {
    long long order_id = 0;
    int side = 0;
    long long quantity = 0;
    double fill_price = 0.0;
    double fee = 0.0;
    double realized_pnl = 0.0;
};

struct Account {
    double cash = 0.0;
    double commission_bps = 0.0;
    double minimum_commission = 0.0;
    double sell_tax_bps = 0.0;
    double slippage_bps = 0.0;
    double realized_pnl = 0.0;
    double total_fees = 0.0;
    std::unordered_map<std::string, Position> positions;
    std::unordered_map<std::string, double> marks;
    std::unordered_set<std::string> halted;
    std::vector<PendingOrder> pending;
    std::vector<FillEvent> last_fills;
    long long next_order_id = 1;
};

Account* account(void* handle) { return static_cast<Account*>(handle); }
const Account* account(const void* handle) { return static_cast<const Account*>(handle); }

double reserved_buy_cash(const Account& state) {
    double result = 0.0;
    for (const auto& order : state.pending) {
        if (order.side != 1) continue;
        const double notional = order.limit_price * order.remaining;
        result += notional + hq_transaction_cost(
            notional, 1, state.commission_bps, state.minimum_commission,
            state.sell_tax_bps);
    }
    return result;
}

long long reserved_sell_quantity(const Account& state, const std::string& symbol) {
    long long result = 0;
    for (const auto& order : state.pending) {
        if (order.side == -1 && order.symbol == symbol) result += order.remaining;
    }
    return result;
}

int execute_at_fill(Account* state, const std::string& symbol, int side,
                    long long quantity, double fill, double* fee,
                    double* realized_pnl) {
    const double notional = fill * static_cast<double>(quantity);
    const double costs = hq_transaction_cost(
        notional, side, state->commission_bps, state->minimum_commission,
        state->sell_tax_bps);
    double realized = 0.0;
    if (side == 1) {
        if (notional + costs > state->cash + 1e-9) return 2;
        Position& position = state->positions[symbol];
        const double old_basis = position.average_cost * position.quantity;
        position.quantity += quantity;
        position.average_cost = (old_basis + notional + costs) /
                                static_cast<double>(position.quantity);
        state->cash -= notional + costs;
    } else {
        auto found = state->positions.find(symbol);
        if (found == state->positions.end() || found->second.quantity < quantity) return 3;
        Position& position = found->second;
        realized = notional - costs - position.average_cost * quantity;
        state->cash += notional - costs;
        position.quantity -= quantity;
        state->realized_pnl += realized;
        if (position.quantity == 0) {
            state->positions.erase(found);
            state->marks.erase(symbol);
        }
    }
    state->total_fees += costs;
    if (side == 1 || state->positions.find(symbol) != state->positions.end()) {
        state->marks[symbol] = fill;
    }
    if (fee != nullptr) *fee = costs;
    if (realized_pnl != nullptr) *realized_pnl = realized;
    return 0;
}
}

extern "C" {
const char* hq_version() { return "0.4.0"; }

long long hq_order_quantity(double cash, double price, long long lot_size,
                            double max_cash_fraction) {
    if (!valid(cash) || !valid(price) || lot_size <= 0 ||
        !valid(max_cash_fraction) || max_cash_fraction > 1.0) return 0;
    const auto lots = static_cast<long long>(
        std::floor(cash * max_cash_fraction / (price * lot_size)));
    return std::max(0LL, lots * lot_size);
}

double hq_slipped_price(double price, int side, double bps) {
    if (!valid(price) || !std::isfinite(bps) || (side != 1 && side != -1)) return 0.0;
    return price * (1.0 + static_cast<double>(side) * bps / 10000.0);
}

double hq_transaction_cost(double notional, int side, double commission_bps,
                           double minimum_commission, double sell_tax_bps) {
    if (notional < 0 || !std::isfinite(notional) || (side != 1 && side != -1)) return 0.0;
    const double commission = std::max(notional * commission_bps / 10000.0,
                                       minimum_commission);
    return commission + (side == -1 ? notional * sell_tax_bps / 10000.0 : 0.0);
}

int hq_pretrade_check(double cash, double price, long long quantity,
                      double current_gross, double nav, double max_order_notional,
                      double max_gross_leverage) {
    if (!valid(price) || quantity <= 0 || !valid(nav)) return 1;
    const double notional = price * static_cast<double>(quantity);
    if (notional > cash) return 2;
    if (valid(max_order_notional) && notional > max_order_notional) return 3;
    if (current_gross + notional > nav * max_gross_leverage) return 4;
    return 0;
}

double hq_round_trip_pnl(double entry_price, double exit_price, long long quantity,
                         double commission_bps, double minimum_commission,
                         double sell_tax_bps, double slippage_bps) {
    if (!valid(entry_price) || !valid(exit_price) || quantity <= 0) return 0.0;
    const double buy = hq_slipped_price(entry_price, 1, slippage_bps) * quantity;
    const double sell = hq_slipped_price(exit_price, -1, slippage_bps) * quantity;
    return sell - buy
        - hq_transaction_cost(buy, 1, commission_bps, minimum_commission, sell_tax_bps)
        - hq_transaction_cost(sell, -1, commission_bps, minimum_commission, sell_tax_bps);
}

double hq_max_drawdown(const double* nav, std::size_t size) {
    if (nav == nullptr || size == 0) return 0.0;
    double peak = nav[0], worst = 0.0;
    for (std::size_t i = 0; i < size; ++i) {
        if (!valid(nav[i])) continue;
        peak = std::max(peak, nav[i]);
        worst = std::min(worst, nav[i] / peak - 1.0);
    }
    return worst;
}

void* hq_account_create(double initial_cash, double commission_bps,
                        double minimum_commission, double sell_tax_bps,
                        double slippage_bps) {
    if (!valid(initial_cash) || commission_bps < 0.0 || minimum_commission < 0.0 ||
        sell_tax_bps < 0.0 || slippage_bps < 0.0 ||
        !std::isfinite(commission_bps) || !std::isfinite(minimum_commission) ||
        !std::isfinite(sell_tax_bps) || !std::isfinite(slippage_bps)) return nullptr;
    Account* result = new (std::nothrow) Account();
    if (result == nullptr) return nullptr;
    result->cash = initial_cash;
    result->commission_bps = commission_bps;
    result->minimum_commission = minimum_commission;
    result->sell_tax_bps = sell_tax_bps;
    result->slippage_bps = slippage_bps;
    return result;
}

void hq_account_destroy(void* handle) { delete account(handle); }

int hq_account_execute(void* handle, const char* raw_symbol, int side,
                       long long quantity, double reference_price,
                       double* fill_price, double* fee, double* realized_pnl) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        (side != 1 && side != -1) || quantity <= 0 || !valid(reference_price)) return 1;
    try {
        const std::string symbol(raw_symbol);
        if (state->halted.find(symbol) != state->halted.end()) return 5;
        const double fill = hq_slipped_price(reference_price, side, state->slippage_bps);
        double costs = 0.0, realized = 0.0;
        const int code = execute_at_fill(
            state, symbol, side, quantity, fill, &costs, &realized);
        if (code != 0) return code;
        if (fill_price != nullptr) *fill_price = fill;
        if (fee != nullptr) *fee = costs;
        if (realized_pnl != nullptr) *realized_pnl = realized;
        return 0;
    } catch (...) {
        return 4;
    }
}

int hq_account_mark(void* handle, const char* raw_symbol, double price) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' || !valid(price)) return 1;
    const std::string symbol(raw_symbol);
    if (state->positions.find(symbol) == state->positions.end()) return 3;
    state->marks[symbol] = price;
    return 0;
}

double hq_account_cash(void* handle) {
    const Account* state = account(handle);
    return state == nullptr ? 0.0 : state->cash;
}

long long hq_account_quantity(void* handle, const char* raw_symbol) {
    const Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr) return 0;
    const auto found = state->positions.find(std::string(raw_symbol));
    return found == state->positions.end() ? 0LL : found->second.quantity;
}

double hq_account_average_cost(void* handle, const char* raw_symbol) {
    const Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr) return 0.0;
    const auto found = state->positions.find(std::string(raw_symbol));
    return found == state->positions.end() ? 0.0 : found->second.average_cost;
}

double hq_account_realized_pnl(void* handle) {
    const Account* state = account(handle);
    return state == nullptr ? 0.0 : state->realized_pnl;
}

double hq_account_total_fees(void* handle) {
    const Account* state = account(handle);
    return state == nullptr ? 0.0 : state->total_fees;
}

double hq_account_equity(void* handle) {
    const Account* state = account(handle);
    if (state == nullptr) return 0.0;
    double result = state->cash;
    for (const auto& item : state->positions) {
        const auto mark = state->marks.find(item.first);
        const double price = mark == state->marks.end() ? item.second.average_cost : mark->second;
        result += price * item.second.quantity;
    }
    return result;
}

double hq_account_gross_exposure(void* handle) {
    const Account* state = account(handle);
    if (state == nullptr) return 0.0;
    double result = 0.0;
    for (const auto& item : state->positions) {
        const auto mark = state->marks.find(item.first);
        const double price = mark == state->marks.end() ? item.second.average_cost : mark->second;
        result += std::abs(price * item.second.quantity);
    }
    return result;
}

int hq_account_set_tradable(void* handle, const char* raw_symbol, int tradable) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0') return 1;
    const std::string symbol(raw_symbol);
    if (tradable) state->halted.erase(symbol);
    else state->halted.insert(symbol);
    return 0;
}

long long hq_account_submit_limit(void* handle, const char* raw_symbol, int side,
                                  long long quantity, double limit_price) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        (side != 1 && side != -1) || quantity <= 0 || !valid(limit_price)) return -1;
    const std::string symbol(raw_symbol);
    if (state->halted.find(symbol) != state->halted.end()) return -5;
    if (side == 1) {
        const double notional = limit_price * quantity;
        const double required = notional + hq_transaction_cost(
            notional, 1, state->commission_bps, state->minimum_commission,
            state->sell_tax_bps);
        if (required > state->cash - reserved_buy_cash(*state) + 1e-9) return -2;
    } else {
        const auto found = state->positions.find(symbol);
        const long long available = found == state->positions.end() ? 0LL :
            found->second.quantity - reserved_sell_quantity(*state, symbol);
        if (quantity > available) return -3;
    }
    const long long id = state->next_order_id++;
    state->pending.push_back(PendingOrder{id, symbol, side, quantity, limit_price});
    return id;
}

int hq_account_cancel(void* handle, long long order_id, long long* cancelled_quantity) {
    Account* state = account(handle);
    if (state == nullptr || order_id <= 0) return 1;
    for (auto it = state->pending.begin(); it != state->pending.end(); ++it) {
        if (it->id != order_id) continue;
        if (cancelled_quantity != nullptr) *cancelled_quantity = it->remaining;
        state->pending.erase(it);
        return 0;
    }
    return 3;
}

long long hq_account_order_remaining(void* handle, long long order_id) {
    const Account* state = account(handle);
    if (state == nullptr || order_id <= 0) return -1;
    for (const auto& order : state->pending) {
        if (order.id == order_id) return order.remaining;
    }
    return 0;
}

int hq_account_process_bar(void* handle, const char* raw_symbol,
                           double open, double high, double low, double close,
                           double volume, double max_participation) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        !valid(open) || !valid(high) || !valid(low) || !valid(close) ||
        low > high || volume < 0.0 || !std::isfinite(volume) ||
        max_participation <= 0.0 || max_participation > 1.0 ||
        !std::isfinite(max_participation)) return 1;
    const std::string symbol(raw_symbol);
    state->last_fills.clear();
    if (state->halted.find(symbol) != state->halted.end()) return 5;
    long long available = static_cast<long long>(std::floor(volume * max_participation));
    if (available <= 0) return 0;
    for (auto& order : state->pending) {
        if (available <= 0 || order.symbol != symbol || order.remaining <= 0) continue;
        const bool eligible = order.side == 1 ? low <= order.limit_price : high >= order.limit_price;
        if (!eligible) continue;
        const double base = order.side == 1 ? std::min(open, order.limit_price) :
                                               std::max(open, order.limit_price);
        double fill = hq_slipped_price(base, order.side, state->slippage_bps);
        fill = order.side == 1 ? std::min(fill, order.limit_price) :
                                 std::max(fill, order.limit_price);
        long long quantity = std::min(order.remaining, available);
        double fee = 0.0, realized = 0.0;
        int code = execute_at_fill(state, symbol, order.side, quantity, fill, &fee, &realized);
        while (code == 2 && quantity > 0) {
            --quantity;
            code = quantity > 0 ? execute_at_fill(
                state, symbol, order.side, quantity, fill, &fee, &realized) : 2;
        }
        if (code != 0 || quantity <= 0) continue;
        order.remaining -= quantity;
        available -= quantity;
        state->last_fills.push_back(FillEvent{
            order.id, order.side, quantity, fill, fee, realized});
    }
    state->pending.erase(std::remove_if(
        state->pending.begin(), state->pending.end(),
        [](const PendingOrder& order) { return order.remaining <= 0; }),
        state->pending.end());
    return 0;
}

std::size_t hq_account_last_fill_count(void* handle) {
    const Account* state = account(handle);
    return state == nullptr ? 0U : state->last_fills.size();
}

int hq_account_last_fill(void* handle, std::size_t index,
                         long long* order_id, int* side, long long* quantity,
                         double* fill_price, double* fee, double* realized_pnl) {
    const Account* state = account(handle);
    if (state == nullptr) return 1;
    if (index >= state->last_fills.size()) return 3;
    const FillEvent& fill = state->last_fills[index];
    if (order_id != nullptr) *order_id = fill.order_id;
    if (side != nullptr) *side = fill.side;
    if (quantity != nullptr) *quantity = fill.quantity;
    if (fill_price != nullptr) *fill_price = fill.fill_price;
    if (fee != nullptr) *fee = fill.fee;
    if (realized_pnl != nullptr) *realized_pnl = fill.realized_pnl;
    return 0;
}

int hq_account_apply_split(void* handle, const char* raw_symbol, double ratio,
                           double cash_in_lieu_price, double* cash_in_lieu) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        !valid(ratio) || cash_in_lieu_price < 0.0 || !std::isfinite(cash_in_lieu_price)) return 1;
    const std::string symbol(raw_symbol);
    auto found = state->positions.find(symbol);
    double credit = 0.0;
    if (found != state->positions.end()) {
        const long long old_quantity = found->second.quantity;
        const double exact_quantity = old_quantity * ratio;
        const long long new_quantity = static_cast<long long>(std::floor(exact_quantity + 1e-9));
        const double fractional = exact_quantity - new_quantity;
        credit = fractional * cash_in_lieu_price;
        const double removed_old_shares = fractional / ratio;
        state->realized_pnl += credit - removed_old_shares * found->second.average_cost;
        state->cash += credit;
        found->second.quantity = new_quantity;
        found->second.average_cost /= ratio;
        if (new_quantity == 0) state->positions.erase(found);
    }
    auto mark = state->marks.find(symbol);
    if (mark != state->marks.end()) mark->second /= ratio;
    for (auto& order : state->pending) {
        if (order.symbol != symbol) continue;
        order.remaining = static_cast<long long>(std::floor(order.remaining * ratio + 1e-9));
        order.limit_price /= ratio;
    }
    state->pending.erase(std::remove_if(
        state->pending.begin(), state->pending.end(),
        [](const PendingOrder& order) { return order.remaining <= 0; }),
        state->pending.end());
    if (cash_in_lieu != nullptr) *cash_in_lieu = credit;
    return 0;
}

int hq_account_credit_income(void* handle, double amount) {
    Account* state = account(handle);
    if (state == nullptr || !std::isfinite(amount) || amount < 0.0) return 1;
    state->cash += amount;
    state->realized_pnl += amount;
    return 0;
}

int hq_account_credit_shares(void* handle, const char* raw_symbol,
                            long long quantity, double reference_price) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        quantity <= 0 || !valid(reference_price)) return 1;
    Position& position = state->positions[std::string(raw_symbol)];
    const double basis = position.average_cost * position.quantity;
    position.quantity += quantity;
    position.average_cost = basis / position.quantity;
    state->marks[std::string(raw_symbol)] = reference_price;
    return 0;
}

int hq_account_apply_dividend(void* handle, const char* raw_symbol,
                              double amount_per_share, double withholding_bps,
                              double* cash_credit) {
    Account* state = account(handle);
    if (state == nullptr || raw_symbol == nullptr || raw_symbol[0] == '\0' ||
        amount_per_share < 0.0 || withholding_bps < 0.0 || withholding_bps > 10000.0 ||
        !std::isfinite(amount_per_share) || !std::isfinite(withholding_bps)) return 1;
    const std::string symbol(raw_symbol);
    const auto found = state->positions.find(symbol);
    if (found == state->positions.end()) return 3;
    const double credit = found->second.quantity * amount_per_share *
                          (1.0 - withholding_bps / 10000.0);
    state->cash += credit;
    state->realized_pnl += credit;
    if (cash_credit != nullptr) *cash_credit = credit;
    return 0;
}
}
