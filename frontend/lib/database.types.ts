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
      brand_aliases: {
        Row: {
          alias: string
          brand_id: string
        }
        Insert: {
          alias: string
          brand_id: string
        }
        Update: {
          alias?: string
          brand_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "brand_aliases_brand_id_fkey"
            columns: ["brand_id"]
            isOneToOne: false
            referencedRelation: "brands"
            referencedColumns: ["id"]
          },
        ]
      }
      brands: {
        Row: {
          created_at: string | null
          id: string
          name: string
        }
        Insert: {
          created_at?: string | null
          id?: string
          name: string
        }
        Update: {
          created_at?: string | null
          id?: string
          name?: string
        }
        Relationships: []
      }
      social_accounts: {
        Row: {
          follower_count: number | null
          followers_captured_at: string | null
          handle: string | null
          id: string
          last_updated: string | null
          platform: string
          profile_url: string | null
          talent_id: string
        }
        Insert: {
          follower_count?: number | null
          followers_captured_at?: string | null
          handle?: string | null
          id?: string
          last_updated?: string | null
          platform: string
          profile_url?: string | null
          talent_id: string
        }
        Update: {
          follower_count?: number | null
          followers_captured_at?: string | null
          handle?: string | null
          id?: string
          last_updated?: string | null
          platform?: string
          profile_url?: string | null
          talent_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "social_accounts_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "social_accounts_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents_search"
            referencedColumns: ["id"]
          },
        ]
      }
      talent_brands: {
        Row: {
          brand_id: string
          confidence: string | null
          evidence_year: number | null
          extracted_at: string | null
          extraction_method: string | null
          raw: Json | null
          source_url: string | null
          status: string | null
          talent_id: string
        }
        Insert: {
          brand_id: string
          confidence?: string | null
          evidence_year?: number | null
          extracted_at?: string | null
          extraction_method?: string | null
          raw?: Json | null
          source_url?: string | null
          status?: string | null
          talent_id: string
        }
        Update: {
          brand_id?: string
          confidence?: string | null
          evidence_year?: number | null
          extracted_at?: string | null
          extraction_method?: string | null
          raw?: Json | null
          source_url?: string | null
          status?: string | null
          talent_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "talent_brands_brand_id_fkey"
            columns: ["brand_id"]
            isOneToOne: false
            referencedRelation: "brands"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "talent_brands_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "talent_brands_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents_search"
            referencedColumns: ["id"]
          },
        ]
      }
      talent_works: {
        Row: {
          role: string | null
          talent_id: string
          work_id: string
        }
        Insert: {
          role?: string | null
          talent_id: string
          work_id: string
        }
        Update: {
          role?: string | null
          talent_id?: string
          work_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "talent_works_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "talent_works_talent_id_fkey"
            columns: ["talent_id"]
            isOneToOne: false
            referencedRelation: "talents_search"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "talent_works_work_id_fkey"
            columns: ["work_id"]
            isOneToOne: false
            referencedRelation: "works"
            referencedColumns: ["id"]
          },
        ]
      }
      talents: {
        Row: {
          active_countries: string[] | null
          birth_year: number | null
          brands_checked_at: string | null
          created_at: string | null
          debut_year: number | null
          gender: string | null
          group_name: string | null
          id: string
          languages_spoken: string[] | null
          last_updated: string | null
          name_en: string
          name_native: string | null
          nationality: string | null
          occupation: string[] | null
          other_names: string[] | null
          photo_source: string | null
          photo_url: string | null
          remarks: string | null
          source: string | null
          wikidata_id: string | null
        }
        Insert: {
          active_countries?: string[] | null
          birth_year?: number | null
          brands_checked_at?: string | null
          created_at?: string | null
          debut_year?: number | null
          gender?: string | null
          group_name?: string | null
          id?: string
          languages_spoken?: string[] | null
          last_updated?: string | null
          name_en: string
          name_native?: string | null
          nationality?: string | null
          occupation?: string[] | null
          other_names?: string[] | null
          photo_source?: string | null
          photo_url?: string | null
          remarks?: string | null
          source?: string | null
          wikidata_id?: string | null
        }
        Update: {
          active_countries?: string[] | null
          birth_year?: number | null
          brands_checked_at?: string | null
          created_at?: string | null
          debut_year?: number | null
          gender?: string | null
          group_name?: string | null
          id?: string
          languages_spoken?: string[] | null
          last_updated?: string | null
          name_en?: string
          name_native?: string | null
          nationality?: string | null
          occupation?: string[] | null
          other_names?: string[] | null
          photo_source?: string | null
          photo_url?: string | null
          remarks?: string | null
          source?: string | null
          wikidata_id?: string | null
        }
        Relationships: []
      }
      works: {
        Row: {
          created_at: string | null
          id: string
          title: string
          type: string | null
          year: number | null
        }
        Insert: {
          created_at?: string | null
          id?: string
          title: string
          type?: string | null
          year?: number | null
        }
        Update: {
          created_at?: string | null
          id?: string
          title?: string
          type?: string | null
          year?: number | null
        }
        Relationships: []
      }
    }
    Views: {
      talents_search: {
        Row: {
          active_countries: string[] | null
          age: number | null
          birth_year: number | null
          brand_names: string[] | null
          brands: Json | null
          brands_checked_at: string | null
          created_at: string | null
          debut_year: number | null
          douyin_followers: number | null
          douyin_followers_captured_at: string | null
          douyin_handle: string | null
          gender: string | null
          group_name: string | null
          id: string | null
          instagram_followers: number | null
          instagram_followers_captured_at: string | null
          instagram_username: string | null
          languages_spoken: string[] | null
          last_updated: string | null
          name_en: string | null
          name_native: string | null
          nationality: string | null
          occupation: string[] | null
          other_names: string[] | null
          other_names_text: string | null
          photo_source: string | null
          photo_url: string | null
          remarks: string | null
          source: string | null
          twitter_followers: number | null
          twitter_followers_captured_at: string | null
          twitter_handle: string | null
          weibo_followers: number | null
          weibo_followers_captured_at: string | null
          weibo_handle: string | null
          wikidata_id: string | null
          xhs_followers: number | null
          xhs_followers_captured_at: string | null
          xhs_handle: string | null
          youtube_followers: number | null
          youtube_followers_captured_at: string | null
          youtube_handle: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      show_limit: { Args: never; Returns: number }
      show_trgm: { Args: { "": string }; Returns: string[] }
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
