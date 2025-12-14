/**
 * TypeScript type definitions matching backend Pydantic models.
 */

export type EventCategory = "politics" | "conflict" | "culture" | "science" | "economics" | "other";

export interface BBox {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface Viewport {
  bbox: BBox;
  zoom: number;
}

export interface Pin {
  event_id: string;
  title: string;
  date: string;
  lat: number;
  lng: number;
  location_label: string;
  category: EventCategory;
  significance_score: number;
  one_liner: string;
  confidence: number;
  positivity_scale: number;
  related_event_ids?: string[] | null;
}

export interface EventDetail {
  event_id: string;
  title: string;
  who: string[];
  what: string;
  when: string;
  where: string;
  why_it_matters: string[];
  timeline: string[];
  key_terms: string[];
  suggested_questions: string[];
}

export interface PinsRequest {
  date: string;
  language: string;
  max_pins: number;
  viewport: Viewport;
}

export interface PinsResponse {
  date: string;
  pins: Pin[];
}

export interface ChatRequest {
  language: string;
  question: string;
  history: ChatMessage[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

