//+------------------------------------------------------------------+
//| BotScalpXTypes.mqh - Shared type definitions                     |
//+------------------------------------------------------------------+
#ifndef BOT_SCALP_X_TYPES_MQH
#define BOT_SCALP_X_TYPES_MQH

struct OrderRequest
  {
   string   action;      // place_order | cancel_order | get_positions
   string   symbol;
   double   volume;
   double   sl;
   double   tp;
   double   price;       // For limit orders
   string   direction;   // LONG | SHORT
   string   idem_key;    // Idempotency key
  };

struct OrderResponse
  {
   int      ticket;
   double   price;
   double   volume;
   int      retcode;
   string   status;      // OK | ERROR | REJECTED
   string   comment;
  };

#endif
