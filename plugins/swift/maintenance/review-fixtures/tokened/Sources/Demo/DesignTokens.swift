import SwiftUI

public enum DesignTokens {
    public enum Spacing {
        public static let xs: CGFloat = 4
        public static let s: CGFloat = 8
        public static let m: CGFloat = 12
        public static let l: CGFloat = 20
    }

    public enum Radius {
        public static let card: CGFloat = 14
    }

    public enum Palette {
        public static let brand = Color(red: 0.12, green: 0.36, blue: 0.62)
        public static let success = Color(red: 0.18, green: 0.62, blue: 0.34)
        public static let danger = Color(red: 0.78, green: 0.20, blue: 0.18)
        public static let surface = Color(red: 0.96, green: 0.96, blue: 0.97)
    }

    public enum Motion {
        public static let standard = Animation.smooth(duration: 0.3)
    }
}
