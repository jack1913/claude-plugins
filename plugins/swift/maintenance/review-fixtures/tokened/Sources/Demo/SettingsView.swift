import SwiftUI

public struct SettingsView: View {
    @State private var editingName = false
    @State private var name = "Jordan Lee"
    let isSynced: Bool

    public init(isSynced: Bool = true) {
        self.isSynced = isSynced
    }

    public var body: some View {
        NavigationStack {
            Form {
                Section("Account") {
                    HStack {
                        LabeledContent("Name", value: name)
                        Button {
                            editingName = true
                        } label: {
                            Image(systemName: "pencil")
                        }
                        .buttonStyle(.plain)
                        .frame(width: 28, height: 28)
                        .accessibilityLabel("Edit name")
                    }
                    LabeledContent("Email", value: "jordan@example.com")
                }
                Section("Sync") {
                    HStack {
                        Text("Status")
                        Spacer()
                        Circle()
                            .fill(isSynced ? DesignTokens.Palette.success : DesignTokens.Palette.danger)
                            .frame(width: DesignTokens.Spacing.s, height: DesignTokens.Spacing.s)
                    }
                }
                Section("Storage") {
                    ProgressView(value: 3.2, total: 5) {
                        Text("Used")
                    } currentValueLabel: {
                        Text("3.2 GB of 5 GB")
                    }
                    .tint(DesignTokens.Palette.brand)
                    .padding(.vertical, DesignTokens.Spacing.xs)
                }
                Section {
                    Button("Delete Account", role: .destructive) {}
                }
            }
            .formStyle(.grouped)
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Save") {}
                        .buttonStyle(.borderedProminent)
                }
            }
            .animation(DesignTokens.Motion.standard, value: isSynced)
            .sheet(isPresented: $editingName) {
                EditNameSheet(name: $name)
            }
        }
    }
}

struct EditNameSheet: View {
    @Binding var name: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: $name)
            }
            .navigationTitle("Edit Name")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}
