export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      ai_chat_history: {
        Row: {
          content: string
          created_at: string
          id: number
          lang: string | null
          lesson_title: string | null
          model: string | null
          provider: string | null
          role: string
          tokens_in: number | null
          tokens_out: number | null
          user_id: string
        }
        Insert: {
          content: string
          created_at?: string
          id?: never
          lang?: string | null
          lesson_title?: string | null
          model?: string | null
          provider?: string | null
          role: string
          tokens_in?: number | null
          tokens_out?: number | null
          user_id: string
        }
        Update: {
          content?: string
          created_at?: string
          id?: never
          lang?: string | null
          lesson_title?: string | null
          model?: string | null
          provider?: string | null
          role?: string
          tokens_in?: number | null
          tokens_out?: number | null
          user_id?: string
        }
        Relationships: []
      }
      ai_usage: {
        Row: {
          message_count: number
          tokens_in: number
          tokens_out: number
          updated_at: string
          usage_date: string
          user_id: string
        }
        Insert: {
          message_count?: number
          tokens_in?: number
          tokens_out?: number
          updated_at?: string
          usage_date: string
          user_id: string
        }
        Update: {
          message_count?: number
          tokens_in?: number
          tokens_out?: number
          updated_at?: string
          usage_date?: string
          user_id?: string
        }
        Relationships: []
      }
      alert_events: {
        Row: {
          alert_id: number | null
          alert_type: string
          body: string
          channel: string
          created_at: string
          delivered_at: string | null
          id: number
          payload: Json
          read_at: string | null
          symbol: string | null
          title: string
          user_id: string
        }
        Insert: {
          alert_id?: number | null
          alert_type: string
          body: string
          channel?: string
          created_at?: string
          delivered_at?: string | null
          id?: number
          payload?: Json
          read_at?: string | null
          symbol?: string | null
          title: string
          user_id: string
        }
        Update: {
          alert_id?: number | null
          alert_type?: string
          body?: string
          channel?: string
          created_at?: string
          delivered_at?: string | null
          id?: number
          payload?: Json
          read_at?: string | null
          symbol?: string | null
          title?: string
          user_id?: string
        }
        Relationships: []
      }
      in_app_notifications: {
        Row: {
          body: string
          created_at: string
          id: number
          kind: string
          link: string | null
          read: boolean
          title: string
          user_id: string
        }
        Insert: {
          body: string
          created_at?: string
          id?: number
          kind: string
          link?: string | null
          read?: boolean
          title: string
          user_id: string
        }
        Update: {
          body?: string
          created_at?: string
          id?: number
          kind?: string
          link?: string | null
          read?: boolean
          title?: string
          user_id?: string
        }
        Relationships: []
      }
      plan_features: {
        Row: {
          ai_reports_per_period: number | null
          ai_reports_period: string | null
          ai_tutor_daily_limit: number | null
          description: string | null
          has_api_access: boolean
          has_email_alerts: boolean
          has_export: boolean
          has_multi_currency: boolean
          has_push_alerts: boolean
          has_realtime_psx: boolean
          has_screener_full: boolean
          has_webhook_integration: boolean
          max_bills: number
          max_budgets: number
          max_finance_history_days: number
          max_goals: number
          max_holdings_per_portfolio: number
          max_portfolios: number
          max_price_alerts: number
          max_watchlist: number
          plan: string
          rank: number
          updated_at: string
        }
        Insert: {
          ai_reports_per_period?: number | null
          ai_reports_period?: string | null
          ai_tutor_daily_limit?: number | null
          description?: string | null
          has_api_access?: boolean
          has_email_alerts?: boolean
          has_export?: boolean
          has_multi_currency?: boolean
          has_push_alerts?: boolean
          has_realtime_psx?: boolean
          has_screener_full?: boolean
          has_webhook_integration?: boolean
          max_bills: number
          max_budgets: number
          max_finance_history_days: number
          max_goals: number
          max_holdings_per_portfolio: number
          max_portfolios: number
          max_price_alerts: number
          max_watchlist: number
          plan: string
          rank: number
          updated_at?: string
        }
        Update: {
          ai_reports_per_period?: number | null
          ai_reports_period?: string | null
          ai_tutor_daily_limit?: number | null
          description?: string | null
          has_api_access?: boolean
          has_email_alerts?: boolean
          has_export?: boolean
          has_multi_currency?: boolean
          has_push_alerts?: boolean
          has_realtime_psx?: boolean
          has_screener_full?: boolean
          has_webhook_integration?: boolean
          max_bills?: number
          max_budgets?: number
          max_finance_history_days?: number
          max_goals?: number
          max_holdings_per_portfolio?: number
          max_portfolios?: number
          max_price_alerts?: number
          max_watchlist?: number
          plan?: string
          rank?: number
          updated_at?: string
        }
        Relationships: []
      }
      price_alerts: {
        Row: {
          condition: string
          created_at: string
          enabled: boolean
          id: number
          last_triggered_at: string | null
          notes: string | null
          notify_email: boolean
          notify_push: boolean
          one_time: boolean
          price: number
          symbol: string
          triggered_at: string | null
          user_id: string
        }
        Insert: {
          condition: string
          created_at?: string
          enabled?: boolean
          id?: number
          last_triggered_at?: string | null
          notes?: string | null
          notify_email?: boolean
          notify_push?: boolean
          one_time?: boolean
          price: number
          symbol: string
          triggered_at?: string | null
          user_id: string
        }
        Update: {
          condition?: string
          created_at?: string
          enabled?: boolean
          id?: number
          last_triggered_at?: string | null
          notes?: string | null
          notify_email?: boolean
          notify_push?: boolean
          one_time?: boolean
          price?: number
          symbol?: string
          triggered_at?: string | null
          user_id?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          display_name: string | null
          id: string
          plan: string
          plan_selected_at: string | null
          tier: string | null
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id: string
          plan?: string
          plan_selected_at?: string | null
          tier?: string | null
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id?: string
          plan?: string
          plan_selected_at?: string | null
          tier?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      psx_alerts: {
        Row: {
          condition: string
          created_at: string
          enabled: boolean
          id: number
          symbol: string
          threshold: number | null
          type: string
          user_id: string | null
        }
        Insert: {
          condition: string
          created_at?: string
          enabled?: boolean
          id?: number
          symbol: string
          threshold?: number | null
          type: string
          user_id?: string | null
        }
        Update: {
          condition?: string
          created_at?: string
          enabled?: boolean
          id?: number
          symbol?: string
          threshold?: number | null
          type?: string
          user_id?: string | null
        }
        Relationships: []
      }
      psx_announcements: {
        Row: {
          body_cached: string | null
          category: string | null
          id: string
          posted_at: string
          refreshed_at: string
          symbol: string | null
          title: string
          url: string | null
        }
        Insert: {
          body_cached?: string | null
          category?: string | null
          id: string
          posted_at?: string
          refreshed_at?: string
          symbol?: string | null
          title?: string
          url?: string | null
        }
        Update: {
          body_cached?: string | null
          category?: string | null
          id?: string
          posted_at?: string
          refreshed_at?: string
          symbol?: string | null
          title?: string
          url?: string | null
        }
        Relationships: []
      }
      psx_dividends: {
        Row: {
          announcement_date: string | null
          announcement_id: string
          bonus_pct: number | null
          ex_date: string | null
          payout_type: string | null
          per_share: number | null
          refreshed_at: string
          symbol: string
        }
        Insert: {
          announcement_date?: string | null
          announcement_id: string
          bonus_pct?: number | null
          ex_date?: string | null
          payout_type?: string | null
          per_share?: number | null
          refreshed_at?: string
          symbol: string
        }
        Update: {
          announcement_date?: string | null
          announcement_id?: string
          bonus_pct?: number | null
          ex_date?: string | null
          payout_type?: string | null
          per_share?: number | null
          refreshed_at?: string
          symbol?: string
        }
        Relationships: []
      }
      psx_fundamentals: {
        Row: {
          div_yield: number | null
          eps: number | null
          payout: number | null
          pb: number | null
          pe: number | null
          refreshed_at: string
          roe: number | null
          symbol: string
        }
        Insert: {
          div_yield?: number | null
          eps?: number | null
          payout?: number | null
          pb?: number | null
          pe?: number | null
          refreshed_at?: string
          roe?: number | null
          symbol: string
        }
        Update: {
          div_yield?: number | null
          eps?: number | null
          payout?: number | null
          pb?: number | null
          pe?: number | null
          refreshed_at?: string
          roe?: number | null
          symbol?: string
        }
        Relationships: []
      }
      psx_holdings: {
        Row: {
          avg_cost: number
          id: number
          portfolio_id: number | null
          purchased_at: string | null
          shares: number
          symbol: string
        }
        Insert: {
          avg_cost?: number
          id?: number
          portfolio_id?: number | null
          purchased_at?: string | null
          shares?: number
          symbol: string
        }
        Update: {
          avg_cost?: number
          id?: number
          portfolio_id?: number | null
          purchased_at?: string | null
          shares?: number
          symbol?: string
        }
        Relationships: [
          {
            foreignKeyName: "psx_holdings_portfolio_id_fkey"
            columns: ["portfolio_id"]
            isOneToOne: false
            referencedRelation: "psx_portfolios"
            referencedColumns: ["id"]
          },
        ]
      }
      psx_index_eod: {
        Row: {
          close: number | null
          code: string
          date: string
          high: number
          low: number
          open: number
          volume: number | null
        }
        Insert: {
          close?: number | null
          code: string
          date: string
          high?: number
          low?: number
          open?: number
          volume?: number | null
        }
        Update: {
          close?: number | null
          code?: string
          date?: string
          high?: number
          low?: number
          open?: number
          volume?: number | null
        }
        Relationships: []
      }
      psx_market_snapshot: {
        Row: {
          change: number | null
          change_pct: number | null
          day_high: number | null
          day_low: number | null
          id: number
          price: number | null
          refreshed_at: string
          symbol: string
          volume: number | null
        }
        Insert: {
          change?: number | null
          change_pct?: number | null
          day_high?: number | null
          day_low?: number | null
          id?: number
          price?: number | null
          refreshed_at?: string
          symbol: string
          volume?: number | null
        }
        Update: {
          change?: number | null
          change_pct?: number | null
          day_high?: number | null
          day_low?: number | null
          id?: number
          price?: number | null
          refreshed_at?: string
          symbol?: string
          volume?: number | null
        }
        Relationships: []
      }
      psx_ohlcv: {
        Row: {
          close: number | null
          date: string
          high: number | null
          id: number
          low: number | null
          open: number | null
          symbol: string
          volume: number | null
        }
        Insert: {
          close?: number | null
          date: string
          high?: number | null
          id?: number
          low?: number | null
          open?: number | null
          symbol: string
          volume?: number | null
        }
        Update: {
          close?: number | null
          date?: string
          high?: number | null
          id?: number
          low?: number | null
          open?: number | null
          symbol?: string
          volume?: number | null
        }
        Relationships: []
      }
      psx_portfolios: {
        Row: {
          created_at: string
          id: number
          name: string
          user_id: string | null
        }
        Insert: {
          created_at?: string
          id?: number
          name: string
          user_id?: string | null
        }
        Update: {
          created_at?: string
          id?: number
          name?: string
          user_id?: string | null
        }
        Relationships: []
      }
      psx_profile: {
        Row: {
          free_float: number | null
          listed_shares: number | null
          logoid: string | null
          name: string
          refreshed_at: string
          sector: string | null
          symbol: string
        }
        Insert: {
          free_float?: number | null
          listed_shares?: number | null
          logoid?: string | null
          name?: string
          refreshed_at?: string
          sector?: string | null
          symbol: string
        }
        Update: {
          free_float?: number | null
          listed_shares?: number | null
          logoid?: string | null
          name?: string
          refreshed_at?: string
          sector?: string | null
          symbol?: string
        }
        Relationships: []
      }
      psx_signals: {
        Row: {
          confidence: number
          features_used: string[] | null
          model_version: string | null
          predicted_at: string
          probabilities: Json | null
          signal: string
          symbol: string
        }
        Insert: {
          confidence: number
          features_used?: string[] | null
          model_version?: string | null
          predicted_at?: string
          probabilities?: Json | null
          signal: string
          symbol: string
        }
        Update: {
          confidence?: number
          features_used?: string[] | null
          model_version?: string | null
          predicted_at?: string
          probabilities?: Json | null
          signal?: string
          symbol?: string
        }
        Relationships: []
      }
      psx_ticks: {
        Row: {
          created_at: string
          id: number
          price: number | null
          symbol: string
          time: string
          volume: number | null
        }
        Insert: {
          created_at?: string
          id?: number
          price?: number | null
          symbol: string
          time?: string
          volume?: number | null
        }
        Update: {
          created_at?: string
          id?: number
          price?: number | null
          symbol?: string
          time?: string
          volume?: number | null
        }
        Relationships: []
      }
      psx_watchlist: {
        Row: {
          created_at: string
          symbol: string
          user_id: string
        }
        Insert: {
          created_at?: string
          symbol: string
          user_id: string
        }
        Update: {
          created_at?: string
          symbol?: string
          user_id?: string
        }
        Relationships: []
      }
      stock_transactions: {
        Row: {
          created_at: string
          executed_at: string
          fees: number
          id: number
          notes: string | null
          portfolio_id: number
          price: number
          quantity: number
          side: string
          source: string
          symbol: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          executed_at?: string
          fees?: number
          id?: number
          notes?: string | null
          portfolio_id: number
          price: number
          quantity: number
          side: string
          source?: string
          symbol: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          executed_at?: string
          fees?: number
          id?: number
          notes?: string | null
          portfolio_id?: number
          price?: number
          quantity?: number
          side?: string
          source?: string
          symbol?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "stock_transactions_portfolio_id_fkey"
            columns: ["portfolio_id"]
            isOneToOne: false
            referencedRelation: "psx_portfolios"
            referencedColumns: ["id"]
          },
        ]
      }
      user_alerts: {
        Row: {
          created_at: string
          enabled: boolean
          id: number
          meta: Json
          title: string
          triggered_at: string | null
          type: string
          user_id: string
        }
        Insert: {
          created_at?: string
          enabled?: boolean
          id?: number
          meta?: Json
          title: string
          triggered_at?: string | null
          type: string
          user_id: string
        }
        Update: {
          created_at?: string
          enabled?: boolean
          id?: number
          meta?: Json
          title?: string
          triggered_at?: string | null
          type?: string
          user_id?: string
        }
        Relationships: []
      }
      user_bills: {
        Row: {
          amount: number
          created_at: string
          currency: string
          due_date: string | null
          id: number
          name: string
          paid_at: string | null
          recurring: boolean
          status: string
          user_id: string
        }
        Insert: {
          amount: number
          created_at?: string
          currency?: string
          due_date?: string | null
          id?: number
          name: string
          paid_at?: string | null
          recurring?: boolean
          status?: string
          user_id: string
        }
        Update: {
          amount?: number
          created_at?: string
          currency?: string
          due_date?: string | null
          id?: number
          name?: string
          paid_at?: string | null
          recurring?: boolean
          status?: string
          user_id?: string
        }
        Relationships: []
      }
      user_budgets: {
        Row: {
          category: string
          created_at: string
          id: number
          limit_amount: number
          period: string
          spent: number
          tip: string | null
          user_id: string
        }
        Insert: {
          category: string
          created_at?: string
          id?: number
          limit_amount?: number
          period?: string
          spent?: number
          tip?: string | null
          user_id: string
        }
        Update: {
          category?: string
          created_at?: string
          id?: number
          limit_amount?: number
          period?: string
          spent?: number
          tip?: string | null
          user_id?: string
        }
        Relationships: []
      }
      user_goals: {
        Row: {
          ai_tip: string | null
          color: string
          created_at: string
          emoji: string
          id: number
          name: string
          saved: number
          target: number
          target_date: string | null
          user_id: string
        }
        Insert: {
          ai_tip?: string | null
          color?: string
          created_at?: string
          emoji?: string
          id?: number
          name: string
          saved?: number
          target: number
          target_date?: string | null
          user_id: string
        }
        Update: {
          ai_tip?: string | null
          color?: string
          created_at?: string
          emoji?: string
          id?: number
          name?: string
          saved?: number
          target?: number
          target_date?: string | null
          user_id?: string
        }
        Relationships: []
      }
      user_notification_prefs: {
        Row: {
          email_activity: boolean
          email_alerts: boolean
          in_app_alerts: boolean
          push_alerts: boolean
          updated_at: string
          user_id: string
        }
        Insert: {
          email_activity?: boolean
          email_alerts?: boolean
          in_app_alerts?: boolean
          push_alerts?: boolean
          updated_at?: string
          user_id: string
        }
        Update: {
          email_activity?: boolean
          email_alerts?: boolean
          in_app_alerts?: boolean
          push_alerts?: boolean
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_settings: {
        Row: {
          currency: string
          language: string
          monthly_income: number | null
          plan: string
          updated_at: string
          user_id: string
        }
        Insert: {
          currency?: string
          language?: string
          monthly_income?: number | null
          plan?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          currency?: string
          language?: string
          monthly_income?: number | null
          plan?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      user_transactions: {
        Row: {
          amount: number
          category: string
          created_at: string
          currency: string
          id: number
          merchant: string
          note: string | null
          source: string | null
          stock_transaction_id: number | null
          transaction_date: string
          transaction_type: string
          user_id: string
        }
        Insert: {
          amount: number
          category: string
          created_at?: string
          currency?: string
          id?: number
          merchant: string
          note?: string | null
          source?: string | null
          stock_transaction_id?: number | null
          transaction_date?: string
          transaction_type: string
          user_id: string
        }
        Update: {
          amount?: number
          category?: string
          created_at?: string
          currency?: string
          id?: number
          merchant?: string
          note?: string | null
          source?: string | null
          stock_transaction_id?: number | null
          transaction_date?: string
          transaction_type?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_transactions_stock_transaction_id_fkey"
            columns: ["stock_transaction_id"]
            isOneToOne: false
            referencedRelation: "stock_transactions"
            referencedColumns: ["id"]
          },
        ]
      }
      user_watchlist: {
        Row: {
          added_at: string
          id: number
          notes: string | null
          notify_email: boolean
          notify_push: boolean
          symbol: string
          user_id: string
        }
        Insert: {
          added_at?: string
          id?: number
          notes?: string | null
          notify_email?: boolean
          notify_push?: boolean
          symbol: string
          user_id: string
        }
        Update: {
          added_at?: string
          id?: number
          notes?: string | null
          notify_email?: boolean
          notify_push?: boolean
          symbol?: string
          user_id?: string
        }
        Relationships: []
      }
      user_zakat_records: {
        Row: {
          breakdown: Json
          calculated_at: string
          created_at: string
          id: number
          islamic_year: string
          method: string
          net_zakatable_pkr: number
          nisab_value_pkr: number
          rate_pct: number
          total_assets_pkr: number
          total_deductions_pkr: number
          user_id: string
          zakat_due_pkr: number
        }
        Insert: {
          breakdown?: Json
          calculated_at?: string
          created_at?: string
          id?: number
          islamic_year: string
          method: string
          net_zakatable_pkr: number
          nisab_value_pkr: number
          rate_pct: number
          total_assets_pkr: number
          total_deductions_pkr?: number
          user_id: string
          zakat_due_pkr: number
        }
        Update: {
          breakdown?: Json
          calculated_at?: string
          created_at?: string
          id?: number
          islamic_year?: string
          method?: string
          net_zakatable_pkr?: number
          nisab_value_pkr?: number
          rate_pct?: number
          total_assets_pkr?: number
          total_deductions_pkr?: number
          user_id?: string
          zakat_due_pkr?: number
        }
        Relationships: []
      }
      user_zakat_settings: {
        Row: {
          custom_rate_pct: number | null
          include_cash: boolean
          include_investments: boolean
          include_receivables: boolean
          method: string
          nisab_source: string
          nisab_value_pkr: number | null
          notes: string | null
          updated_at: string
          user_id: string
        }
        Insert: {
          custom_rate_pct?: number | null
          include_cash?: boolean
          include_investments?: boolean
          include_receivables?: boolean
          method?: string
          nisab_source?: string
          nisab_value_pkr?: number | null
          notes?: string | null
          updated_at?: string
          user_id: string
        }
        Update: {
          custom_rate_pct?: number | null
          include_cash?: boolean
          include_investments?: boolean
          include_receivables?: boolean
          method?: string
          nisab_source?: string
          nisab_value_pkr?: number | null
          notes?: string | null
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
