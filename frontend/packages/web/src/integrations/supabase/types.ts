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
      finance_transactions: {
        Row: {
          amount: number
          category: string | null
          created_at: string | null
          currency: string | null
          email_subject: string | null
          id: string
          merchant: string | null
          raw_text: string | null
          source: string | null
          transaction_date: string | null
          transaction_type: string | null
          user_id: string
        }
        Insert: {
          amount: number
          category?: string | null
          created_at?: string | null
          currency?: string | null
          email_subject?: string | null
          id?: string
          merchant?: string | null
          raw_text?: string | null
          source?: string | null
          transaction_date?: string | null
          transaction_type?: string | null
          user_id: string
        }
        Update: {
          amount?: number
          category?: string | null
          created_at?: string | null
          currency?: string | null
          email_subject?: string | null
          id?: string
          merchant?: string | null
          raw_text?: string | null
          source?: string | null
          transaction_date?: string | null
          transaction_type?: string | null
          user_id?: string
        }
        Relationships: []
      }
      price_alerts: {
        Row: {
          condition: string
          created_at: string
          enabled: boolean
          id: number
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
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id: string
          plan?: string
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id?: string
          plan?: string
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
          volume: number | null
        }
        Insert: {
          close?: number | null
          code: string
          date: string
          volume?: number | null
        }
        Update: {
          close?: number | null
          code?: string
          date?: string
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
          name: string
          refreshed_at: string
          sector: string | null
          symbol: string
        }
        Insert: {
          free_float?: number | null
          listed_shares?: number | null
          name?: string
          refreshed_at?: string
          sector?: string | null
          symbol: string
        }
        Update: {
          free_float?: number | null
          listed_shares?: number | null
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
      user_watchlist: {
        Row: {
          added_at: string
          id: number
          symbol: string
          user_id: string
        }
        Insert: {
          added_at?: string
          id?: number
          symbol: string
          user_id: string
        }
        Update: {
          added_at?: string
          id?: number
          symbol?: string
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
