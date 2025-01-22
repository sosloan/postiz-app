import {LayoutSettings} from "@gitroom/frontend/components/layout/layout.settings";
import { UserInputForm } from "/components/ui/user-input-form";

export default async function Layout({ children }: { children: React.ReactNode }) {
    /*
     * Replace the elements below with your own.
     *
     * Note: The corresponding styles are in the ./index.scss file.
     */
    return (
        <LayoutSettings>
            <UserInputForm />
            {children}
        </LayoutSettings>
    );
}
