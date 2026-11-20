#pragma once

#include <cstddef>

#if defined(_WIN32)
#define HQ_EXPORT __declspec(dllexport)
#else
#define HQ_EXPORT
#endif

extern "C" {
HQ_EXPORT const char* hq_version();
HQ_EXPORT long long hq_order_quantity(double cash, double price, long long lot_size,
                                      double max_cash_fraction);
HQ_EXPORT double hq_slipped_price(double price, int side, double slippage_bps);
HQ_EXPORT double hq_transaction_cost(double notional, int side, double commission_bps,
                                     double minimum_commission, double sell_tax_bps);
HQ_EXPORT int hq_pretrade_check(double cash, double price, long long quantity,
                                double current_gross, double nav,
                                double max_order_notional, double max_gross_leverage);
HQ_EXPORT double hq_round_trip_pnl(double entry_price, double exit_price, long long quantity,
                                   double commission_bps, double minimum_commission,
                                   double sell_tax_bps, double slippage_bps);
HQ_EXPORT double hq_max_drawdown(const double* nav, std::size_t size);

// Stateful long-only cash account. Return codes: 0=filled, 1=invalid input,
// 2=insufficient cash, 3=insufficient position/not found, 4=internal error,
// 5=symbol halted.
HQ_EXPORT void* hq_account_create(double initial_cash, double commission_bps,
                                  double minimum_commission, double sell_tax_bps,
                                  double slippage_bps);
HQ_EXPORT void hq_account_destroy(void* handle);
HQ_EXPORT int hq_account_execute(void* handle, const char* symbol, int side,
                                 long long quantity, double reference_price,
                                 double* fill_price, double* fee,
                                 double* realized_pnl);
HQ_EXPORT int hq_account_mark(void* handle, const char* symbol, double price);
HQ_EXPORT double hq_account_cash(void* handle);
HQ_EXPORT long long hq_account_quantity(void* handle, const char* symbol);
HQ_EXPORT double hq_account_average_cost(void* handle, const char* symbol);
HQ_EXPORT double hq_account_realized_pnl(void* handle);
HQ_EXPORT double hq_account_total_fees(void* handle);
HQ_EXPORT double hq_account_equity(void* handle);
HQ_EXPORT double hq_account_gross_exposure(void* handle);
HQ_EXPORT int hq_account_set_tradable(void* handle, const char* symbol, int tradable);
HQ_EXPORT long long hq_account_submit_limit(void* handle, const char* symbol, int side,
                                            long long quantity, double limit_price);
HQ_EXPORT int hq_account_cancel(void* handle, long long order_id,
                                long long* cancelled_quantity);
HQ_EXPORT long long hq_account_order_remaining(void* handle, long long order_id);
HQ_EXPORT int hq_account_process_bar(void* handle, const char* symbol,
                                     double open, double high, double low, double close,
                                     double volume, double max_participation);
HQ_EXPORT std::size_t hq_account_last_fill_count(void* handle);
HQ_EXPORT int hq_account_last_fill(void* handle, std::size_t index,
                                   long long* order_id, int* side, long long* quantity,
                                   double* fill_price, double* fee, double* realized_pnl);
HQ_EXPORT int hq_account_apply_split(void* handle, const char* symbol, double ratio,
                                     double cash_in_lieu_price, double* cash_in_lieu);
HQ_EXPORT int hq_account_apply_dividend(void* handle, const char* symbol,
                                        double amount_per_share, double withholding_bps,
                                        double* cash_credit);
// Settle an already-recorded entitlement; independent of shares held at payment.
HQ_EXPORT int hq_account_credit_income(void* handle, double amount);
HQ_EXPORT int hq_account_credit_shares(void* handle, const char* symbol,
                                       long long quantity, double reference_price);
}
