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
            ScrollView {
                SettingsContent(name: name, isSynced: isSynced, editingName: $editingName)
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItemGroup(placement: .primaryAction) {
                    Button("Export") {}
                        .buttonStyle(.borderedProminent)
                    Button("Share") {}
                        .buttonStyle(.borderedProminent)
                    Button("Save") {}
                        .buttonStyle(.borderedProminent)
                }
            }
            .sheet(isPresented: $editingName) {
                EditNameSheet(name: $name)
            }
        }
    }
}

struct SettingsContent: View {
    let name: String
    let isSynced: Bool
    @Binding var editingName: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Account")
                .font(.system(size: 13, weight: .ultraLight))
            HStack {
                Text("Name")
                Spacer()
                Text(name)
                    .foregroundStyle(.secondary)
                Button {
                    editingName = true
                } label: {
                    Image(systemName: "pencil")
                }
                .buttonStyle(.plain)
                .frame(width: 28, height: 28)
            }
            Divider()
            HStack {
                Text("Email")
                Spacer()
                Text("jordan@example.com")
                    .foregroundStyle(.secondary)
            }
            Divider()
            HStack {
                Text("Sync")
                Spacer()
                Circle()
                    .fill(isSynced ? Color.green : Color.red)
                    .frame(width: 10, height: 10)
            }
            Divider()
            VStack(alignment: .leading, spacing: 4) {
                Text("Storage")
                    .font(.headline)
                Text("3.2 GB of 5 GB used")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding()
            .glassEffect(.regular, in: .rect(cornerRadius: 16))
            Button("Delete Account") {}
                .buttonStyle(.borderedProminent)
                .tint(.red)
        }
        .padding()
    }
}

struct EditNameSheet: View {
    @Binding var name: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            TextField("Name", text: $name)
                .padding()
                .navigationTitle("Edit Name")
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }
                    }
                }
        }
    }
}
