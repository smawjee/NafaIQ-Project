import { render } from "@testing-library/react-native";
import { View } from "react-native";

const mockLessonExperience = jest.fn((_props: unknown) => <View testID="lesson-experience" />);
const mockAttempt = jest.fn();

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ projectId: "p1" }),
  useRouter: () => ({ back: jest.fn() }),
}));

jest.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({ colors: { ai: "#00d4aa", warning: "#f5a524", border: "#222", textPrimary: "#fff" } }),
}));

jest.mock("@/hooks/queries/use-learn-studio", () => ({
  useStudioProject: () => ({
    isLoading: false,
    isError: false,
    data: {
      id: "p1", status: "ready", stage: "ready", videoReady: true,
      studyPack: {
        notes: ["Grounded note"],
        lesson: {
          id: "generated-1", title: "PSX Dividends", subtitle: "Learn dividends",
          emoji: "📈", category: "PSX Learning", accent: "#00d4aa", duration: "4 min",
          level: "Beginner", type: "article", presets: [], sections: [], quiz: [],
          origin: "generated", language: "en", sources: [{ sourceId: "s1", title: "PSX" }],
          projectId: "p1", videoStatus: "ready", rewardMode: "practice",
        },
      },
    },
  }),
  useStudioPlayback: () => ({ data: { url: "https://signed.example/lesson.mp4" } }),
  useRecordStudioQuiz: () => ({ mutate: mockAttempt }),
  useRequestStudioVideo: () => ({ mutate: jest.fn(), isPending: false, error: null }),
}));

jest.mock("@/app/(tabs)/learn/lesson/[id]", () => ({
  LessonExperience: (props: unknown) => mockLessonExperience(props),
}));

import GeneratedLessonScreen from "@/app/(tabs)/learn/generated/[projectId]";

describe("GeneratedLessonScreen", () => {
  it("reuses the native lesson experience in practice mode with secure playback", () => {
    const { getByTestId } = render(<GeneratedLessonScreen />);
    expect(getByTestId("lesson-experience")).toBeTruthy();
    expect(mockLessonExperience).toHaveBeenCalledWith(
      expect.objectContaining({
        practice: true,
        lesson: expect.objectContaining({
          title: "PSX Dividends",
          type: "video",
          videoUrl: "https://signed.example/lesson.mp4",
        }),
        sources: [{ sourceId: "s1", title: "PSX" }],
      }),
    );
  });
});
